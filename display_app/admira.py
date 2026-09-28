"""Al encender el PC, Admira abre las pantallas antes de que el servidor conteste y se queda en negro.

Admira arranca desde la carpeta Inicio común, que sin permisos de administrador no se puede
retrasar. Cuando el servidor ya contesta, se reinicia Admira una vez para que cargue las pantallas,
pero solo si acaba de arrancar: si lleva rato abierto, sus pantallas ya se reconectan solas.
"""

from datetime import datetime
import logging
import os
from pathlib import Path
import subprocess

from .audio import NO_WINDOW, reachable

log = logging.getLogger(__name__)
LAUNCHERS = [
    r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp\ADmira.lnk",
    r"%AppData%\Microsoft\Windows\Start Menu\Programs\Startup\ADmira.lnk",
    r"C:\admira\admira.exe",
]
# Admira más antiguo que esto no acaba de arrancar con el equipo: no se toca.
RECENT_MINUTES = 10


def find_launcher(configured=None):
    for candidate in [configured] if configured else LAUNCHERS:
        path = Path(os.path.expandvars(candidate))
        if path.is_file():
            return path
    return None


def started_minutes_ago():
    """Minutos desde que arrancó Admira, o None si no está abierto."""
    script = ("$p = Get-Process admira -ErrorAction SilentlyContinue | Sort-Object StartTime | Select-Object -First 1; "
              "if ($p) { $p.StartTime.ToString('o') }")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
    started = result.stdout.strip()
    if not started:
        return None
    return (datetime.now().astimezone() - datetime.fromisoformat(started)).total_seconds() / 60


def running():
    result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq admira.exe", "/NH"], capture_output=True,
                            text=True, errors="replace", timeout=30, creationflags=NO_WINDOW)
    return "admira.exe" in result.stdout.lower()


def close(stop):
    # Primero se le pide que se cierre; si no lo hace en 10 s, se fuerza.
    for force in ([], ["/F", "/T"]):
        subprocess.run(["taskkill", *force, "/IM", "admira.exe"], capture_output=True, timeout=30,
                       creationflags=NO_WINDOW)
        for _ in range(20):
            if not running():
                return True
            stop.wait(0.5)
    return False


def run_admira(state, stop, port=8002):
    if os.name != "nt":
        state.set_hardware("admira", "disabled", "Solo en Windows")
        return
    state.set_hardware("admira", "waiting", "Esperando al servidor")
    while not stop.is_set() and not reachable(f"http://127.0.0.1:{port}/api/status"):
        stop.wait(0.5)
    if stop.is_set():
        return
    minutes = started_minutes_ago()
    if minutes is None:
        state.set_hardware("admira", "ready", "Admira aún no estaba abierto: cargará la web ya en marcha")
        return
    if minutes > RECENT_MINUTES:
        state.set_hardware("admira", "ready", f"Admira ya llevaba {minutes:.0f} min abierto: no se reinicia")
        return
    launcher = find_launcher(state.settings.admira.launcher)
    if launcher is None:  # Sin forma de volver a abrirlo, no se cierra.
        state.set_hardware("admira", "error", "No se encuentra Admira; configura admira.launcher")
        return
    if not close(stop):
        state.set_hardware("admira", "error", "No se pudo cerrar Admira para reiniciarlo")
        return
    os.startfile(launcher)
    log.info("Admira reiniciado para que cargue las pantallas con el servidor ya en marcha")
    state.set_hardware("admira", "ready", "Reiniciado a las " + datetime.now().strftime("%H:%M")
                       + " con la web ya en marcha")
