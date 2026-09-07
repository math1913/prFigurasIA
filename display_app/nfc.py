"""Lector PC/SC integrado desde NFC-ACR122; sin escrituras XML."""

import json
import logging

from .config import ROOT

log = logging.getLogger(__name__)
GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]


def load_aliases(path):
    with path.open(encoding="utf-8-sig") as source:
        values = json.load(source)
    if not isinstance(values, dict) or not all(isinstance(v, str) for v in values.values()):
        raise ValueError("aliases.json debe contener un mapa UID → nombre")
    return {str(key).replace(" ", "").upper(): value for key, value in values.items()}


class NFCObserver:
    # CardMonitor requiere update(); no importamos pyscard en el modo demo.
    def __init__(self, aliases, state):
        self.aliases = aliases
        self.state = state
        self.present = {}

    def update(self, observable, actions):
        added, removed = actions
        # Primero las retiradas: permite reemplazar tarjetas con el mismo ATR.
        for card in removed:
            key = (str(card.reader), tuple(card.atr))
            info = self.present.pop(key, None)
            if info and self.state.settings.nfc.trigger == "remove":
                self.state.trigger("nfc", info["alias"])
        for card in added:
            key = (str(card.reader), tuple(card.atr))
            self.present.pop(key, None)
            connection = None
            try:
                connection = card.createConnection()
                connection.connect()
                data, sw1, sw2 = connection.transmit(GET_UID_APDU)
                if (sw1, sw2) != (0x90, 0x00) or not data:
                    log.warning("No se pudo obtener el UID en %s", card.reader)
                    continue
                uid = bytes(data).hex().upper()
                alias = self.aliases.get(uid)
                if alias is None:
                    log.info("Tarjeta sin alias: %s", uid)
                    continue
                self.present[key] = {"uid": uid, "alias": alias}
                if self.state.settings.nfc.trigger == "insert":
                    self.state.trigger("nfc", alias)
            except Exception:
                log.exception("Error leyendo tarjeta en %s", card.reader)
            finally:
                if connection:
                    try:
                        connection.disconnect()
                    except Exception:
                        log.debug("La tarjeta ya está desconectada", exc_info=True)
        self.state.set_present(self.present)


def run_nfc(state, stop):
    try:
        from smartcard.CardMonitoring import CardMonitor
        from smartcard.System import readers

        aliases = load_aliases(ROOT / state.settings.nfc.aliases_file)
        missing = set(aliases.values()) - state.settings.channels["nfc"].events.keys()
        if missing:
            raise ValueError(f"Falta contenido NFC para: {sorted(missing)}")
    except Exception as exc:
        log.exception("No se pudo iniciar NFC")
        state.set_hardware("nfc", "error", str(exc))
        return

    while not stop.is_set():
        monitor = observer = None
        try:
            devices = readers()
            if not devices:
                state.set_hardware("nfc", "waiting", "Conecta un lector NFC")
                stop.wait(2)
                continue
            monitor = CardMonitor()
            observer = NFCObserver(aliases, state)
            monitor.addObserver(observer)
            state.set_hardware("nfc", "ready", ", ".join(map(str, devices)))
            while not stop.wait(2):
                if set(map(str, readers())) != set(map(str, devices)):
                    break
        except Exception as exc:
            log.exception("Error en el lector NFC; reintentando")
            state.set_hardware("nfc", "error", str(exc))
            stop.wait(2)
        finally:
            if monitor and observer:
                monitor.deleteObserver(observer)
            state.set_present({})
