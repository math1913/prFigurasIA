"""Estado sincronizado entre sensores y pantallas, con canales independientes."""

from copy import deepcopy
import threading
import time
from uuid import uuid4

from .config import Settings


class DisplayState:
    def __init__(self, settings: Settings, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.lock = threading.RLock()
        self.session = uuid4().hex
        self.active = {name: None for name in settings.channels}
        self.revisions = {name: 0 for name in settings.channels}
        self.hardware = {name: {"status": "starting", "detail": "Iniciando"}
                         for name in ["figuras", "barcode", "nfc", "weather", "audio"]}
        self.present = {}
        self.weather_code = None
        # Desde cuándo suena la base: pantalla y audio del PC la siguen desde el mismo punto.
        self.base_since = {name: clock() for name in settings.channels}
        self.audio_seen = {}

    def _to_base(self, channel):
        self.active[channel] = None
        self.revisions[channel] += 1
        self.base_since[channel] = self.clock()

    def _expire(self, channel):
        event = self.active[channel]
        if event and self.clock() >= event["deadline"]:
            self._to_base(channel)

    def trigger(self, channel: str, key: str, restart=True) -> bool:
        with self.lock:
            config = self.settings.channels[channel]
            if key not in config.events:
                return False
            self._expire(channel)
            active = self.active[channel]
            if not restart and active and active["key"] == key:
                return False  # Sigue sonando: no vuelve al principio.
            self.revisions[channel] += 1
            video = config.events[key]
            seconds = config.max_event_seconds if video.src else config.placeholder_seconds
            self.active[channel] = {
                "key": key, "id": uuid4().hex,
                "started": self.clock(), "deadline": self.clock() + seconds,
            }
            return True

    def complete(self, channel: str, event_id: str) -> bool:
        # Un ended/error tardío del vídeo interrumpido nunca termina el nuevo vídeo.
        with self.lock:
            active = self.active[channel]
            if active is None or active["id"] != event_id:
                return False
            self._to_base(channel)
            return True

    def base_video(self, channel):
        weather = self.settings.weather
        if self.weather_code and channel in weather.base_channels:
            video = weather.videos[self.weather_code]
            if video.src:
                return video
        return self.settings.channels[channel].base

    def set_weather(self, code):
        with self.lock:
            if code is not None and code not in self.settings.weather.videos:
                raise ValueError("Código meteorológico desconocido")
            if code != self.weather_code:
                self.weather_code = code
                for channel in self.settings.weather.base_channels:
                    if self.active[channel] is None:
                        self.revisions[channel] += 1
                        self.base_since[channel] = self.clock()

    def is_idle(self, channel):
        with self.lock:
            self._expire(channel)
            return self.active[channel] is None

    def snapshot(self, channel):
        with self.lock:
            self._expire(channel)
            active = self.active[channel]
            config = self.settings.channels[channel]
            return {
                "channel": channel, "session": self.session,
                "revision": self.revisions[channel],
                "mode": "event" if active else "base",
                "key": active["key"] if active else None,
                "event_id": active["id"] if active else None,
                # Tiempo desde que empezó lo que toca: el evento o, en la base, su bucle.
                "elapsed_seconds": self.clock() - (active["started"] if active else self.base_since[channel]),
                "remaining_ms": max(0, (active["deadline"] - self.clock()) * 1000) if active else 0,
                "content": (config.events[active["key"]] if active else self.base_video(channel)).model_dump(),
                "base": self.base_video(channel).model_dump(),
                "fallback_base": config.base.model_dump(),
                "overlay": channel in self.settings.nfc.overlay_channels,
                "fit": config.fit,
                "audio_on_pc": config.audio_on_pc,
                "audio_delay_ms": config.audio_delay_ms,
            }

    def saw_audio_page(self, channel):
        with self.lock:
            self.audio_seen[channel] = self.clock()

    def audio_page_age(self, channel):
        """Segundos desde la última consulta de /audio/<canal>, o None si nunca ha consultado."""
        with self.lock:
            seen = self.audio_seen.get(channel)
            return None if seen is None else self.clock() - seen

    def set_hardware(self, channel, status, detail):
        with self.lock:
            self.hardware[channel] = {"status": status, "detail": detail}

    def set_present(self, present):
        with self.lock:
            self.present = deepcopy(present)

    def objects(self):
        with self.lock:
            aliases = {item["alias"] for item in self.present.values()}
            return {alias: alias in aliases for alias in self.settings.nfc.monitored_objects}

    def health(self):
        with self.lock:
            return {"hardware": deepcopy(self.hardware), "weather_code": self.weather_code}


class FigureGate:
    """Una acción por aparición estable; no interrumpe el vídeo en cada frame."""

    def __init__(self, stable_seconds, absence_seconds, clock=time.monotonic, cooldown_seconds=60):
        self.stable_seconds = stable_seconds
        self.absence_seconds = absence_seconds
        self.clock = clock
        self.cooldown_seconds = cooldown_seconds
        self.last_triggered = {}
        self.reset_visibility()

    def reset_visibility(self):
        """Reiniciar la detección tras un corte sin olvidar el margen por figura."""
        self.candidate = None
        self.since = 0
        self.seen = set()
        self.absent_since = {}
        self.fired = set()

    def update(self, detections):
        """detections: pares (clave, confianza). Prioriza la mayor confianza."""
        now = self.clock()
        visible = {key for key, _ in detections}
        for key in self.seen - visible:
            self.absent_since.setdefault(key, now)
        for key, since in list(self.absent_since.items()):
            if now - since >= self.absence_seconds:
                self.fired.discard(key)
                self.seen.discard(key)
                del self.absent_since[key]
        for key in visible:
            self.absent_since.pop(key, None)
        self.seen.update(visible)
        selected = max(detections, key=lambda item: item[1])[0] if detections else None
        if selected != self.candidate:
            self.candidate, self.since = selected, now
        if selected and selected not in self.fired and now - self.since >= self.stable_seconds:
            previous = self.last_triggered.get(selected)
            if previous is not None and now - previous < self.cooldown_seconds:
                return None
            self.fired.add(selected)
            self.last_triggered[selected] = now
            return selected
        return None
