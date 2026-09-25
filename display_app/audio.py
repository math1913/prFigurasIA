"""Sonido en el PC: abre /audio/<canal> en un Chrome o Edge sin ventana y lo mantiene abierto.

Sirve a las pantallas con audio_on_pc: la pantalla va en silencio y el sonido sale por los
altavoces de este PC, sincronizado con ella mediante el reloj del servidor.
"""

import ctypes
import logging
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

from .config import ROOT

log = logging.getLogger(__name__)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Chrome y, si no está, Edge: los dos son Chromium y aceptan los mismos argumentos.
BROWSERS = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
]
# Una página que lleva este tiempo sin consultar el estado se da por colgada y se reabre.
SILENT_SECONDS = 30
PROFILES = ROOT / ".audio-browser"


def find_browser(configured=None):
    for candidate in [configured] if configured else BROWSERS:
        path = Path(os.path.expandvars(candidate))
        if path.is_file():
            return path
    return None


def close_strays(profile):
    """Cierra un navegador que siga abierto con este perfil, p. ej. de una ejecución que se cortó.

    Si quedara uno, el nuevo solo le pasaría la URL y se cerraría: otra pestaña sonando a la vez.
    """
    if os.name != "nt":
        return
    script = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--user-data-dir=%s*' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % profile)
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, timeout=30, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        log.warning("No se pudo comprobar si quedaba un navegador de audio abierto")


def tie_to_this_process(process):
    """Windows: un job object cierra el navegador con este proceso, aunque se cierre de golpe."""
    if os.name != "nt":
        return None
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_ulonglong * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    info = Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    # 9 = JobObjectExtendedLimitInformation. El handle del job no se cierra: vive lo que este proceso.
    if not (job and kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
            and kernel32.AssignProcessToJobObject(job, int(process._handle))):
        log.warning("El navegador de audio no quedó atado a la aplicación (error %s)", ctypes.get_last_error())
    return job


def launch(browser, url, profile):
    close_strays(profile)
    process = subprocess.Popen(
        [str(browser), "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
         "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
         # Sin ventana cuenta como segundo plano: que no frene los temporizadores de la página.
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
         "--disable-backgrounding-occluded-windows", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    tie_to_this_process(process)
    return process


def close(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()


def responsive(age):
    return age is not None and age <= 10


def reachable(url):
    try:
        with urlopen(url, timeout=2):
            return True
    except OSError:
        return False


def run_audio(state, stop, port=8002):
    channels = [name for name, channel in state.settings.channels.items() if channel.audio_on_pc]
    if not channels:
        state.set_hardware("audio", "disabled", "Ninguna pantalla con audio_on_pc")
        return
    browser = find_browser(state.settings.audio.browser)
    if browser is None:
        state.set_hardware("audio", "error", "No se encuentra Chrome ni Edge; configura audio.browser")
        return
    server = f"http://127.0.0.1:{port}"
    # El navegador no reintenta una página que no carga: se espera a que el servidor conteste.
    state.set_hardware("audio", "waiting", "Esperando al servidor")
    while not stop.is_set() and not reachable(server + "/api/status"):
        stop.wait(0.5)
    processes = {}
    try:
        while not stop.is_set():
            for channel in channels:
                process, opened = processes.get(channel, (None, 0))
                age = state.audio_page_age(channel)
                hung = (process is not None and time.monotonic() - opened > SILENT_SECONDS
                        and (age is None or age > SILENT_SECONDS))
                if process is None or process.poll() is not None or hung:
                    if process is not None:
                        log.warning("El audio de %s no responde; se vuelve a abrir el navegador", channel)
                        close(process)
                    processes[channel] = (launch(browser, f"{server}/audio/{channel}", PROFILES / channel),
                                          time.monotonic())
            waiting = [name for name in channels if not responsive(state.audio_page_age(name))]
            if waiting:
                state.set_hardware("audio", "waiting", "Abriendo el audio de " + ", ".join(waiting))
            else:
                state.set_hardware("audio", "ready", f"{browser.stem} · " + ", ".join(channels))
            stop.wait(2)
    finally:
        for process, _ in processes.values():
            close(process)
