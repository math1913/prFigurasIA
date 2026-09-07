"""Escáner serie de BarcodeBigBang, conectado al canal de figuras."""

import json
import logging

from .config import ROOT

log = logging.getLogger(__name__)


def load_mapping(path):
    with path.open(encoding="utf-8-sig") as source:
        values = json.load(source)
    if not isinstance(values, dict) or not all(isinstance(v, str) for v in values.values()):
        raise ValueError("barcode_id.json debe contener un mapa código → contenido")
    return {str(code).strip(): value for code, value in values.items()}


def handle_scan(state, code):
    # Conserva la recarga del mapa en cada lectura del proyecto original.
    mapping = load_mapping(ROOT / state.settings.barcode.mapping_file)
    key = mapping.get(code.replace("\x00", "").strip())
    return bool(key and state.trigger("figuras", key))


def select_port(config, ports):
    if config.port:
        return config.port
    matches = [p.device for p in ports if p.vid == config.vid and p.pid == config.pid]
    if len(matches) > 1:
        raise ValueError("Hay varios escáneres iguales; configura barcode.port")
    return matches[0] if matches else None


class ScanBuffer:
    """Acepta CR, LF, CRLF y fragmentos; limita lecturas sin terminador."""

    def __init__(self):
        self.buffer = bytearray()
        self.overflow = False

    def flush(self):
        raw = bytes(self.buffer)
        valid = not self.overflow
        self.buffer.clear()
        self.overflow = False
        try:
            return raw.decode("utf-8").strip() if valid else ""
        except UnicodeDecodeError:
            return ""

    def feed(self, raw):
        codes = []
        for byte in raw:
            if byte in (10, 13):
                code = self.flush()
                if code:
                    codes.append(code)
            elif byte != 0:
                if len(self.buffer) < 512:
                    self.buffer.append(byte)
                else:
                    self.overflow = True
        return codes


def run_barcode(state, stop):
    config = state.settings.barcode
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        state.set_hardware("barcode", "error", str(exc))
        return
    while not stop.is_set():
        try:
            port = select_port(config, list_ports.comports() if not config.port else [])
            if not port:
                state.set_hardware("barcode", "waiting", "Conecta el escáner de códigos de barras")
                stop.wait(2)
                continue
            with serial.Serial(port=port, baudrate=config.baudrate, bytesize=config.bytesize,
                               parity=config.parity, stopbits=config.stopbits,
                               timeout=config.timeout_seconds) as device:
                state.set_hardware("barcode", "ready", port)
                buffer = ScanBuffer()
                while not stop.is_set():
                    raw = device.read(max(1, min(device.in_waiting, 4096)))
                    codes = buffer.feed(raw) if raw else [buffer.flush()]
                    for code in filter(None, codes):
                        try:
                            accepted = handle_scan(state, code)
                            log.info("Código %s: %s", code, "activado" if accepted else "sin contenido asignado")
                            state.set_hardware("barcode", "ready", port)
                        except (OSError, ValueError) as exc:
                            state.set_hardware("barcode", "error", str(exc))
        except Exception as exc:
            log.warning("Escáner no disponible: %s", exc)
            state.set_hardware("barcode", "error", str(exc))
            stop.wait(2)
