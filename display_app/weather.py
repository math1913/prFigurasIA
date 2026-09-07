"""Clima de OpenWeather, conservando los códigos del weatherReader original."""

import json
import logging
import os
import time
from urllib.parse import urlencode
from urllib.request import urlopen

log = logging.getLogger(__name__)


def weather_code(data, now, sunset_seconds=3600):
    code = int(data["weather"][0]["id"])
    sunrise, sunset = data["sys"]["sunrise"], data["sys"]["sunset"]
    if sunrise <= now < sunset:
        return "DL" if code < 800 else "DD" if code == 800 else "DN"
    if sunset <= now < sunset + sunset_seconds:
        return "DL" if code < 800 else "A" if code == 800 else "DN"
    return "NL" if code < 800 else "ND" if code == 800 else "NN"


def run_weather(state, stop):
    config = state.settings.weather
    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        state.set_hardware("weather", "waiting", f"Configura {config.api_key_env}")
        return
    url = "https://api.openweathermap.org/data/2.5/weather?" + urlencode({
        "q": config.city, "appid": api_key, "units": "metric", "lang": "es",
    })
    data, last_success, next_fetch = None, 0, 0
    while not stop.is_set():
        now = time.monotonic()
        if now >= next_fetch:
            try:
                with urlopen(url, timeout=10) as response:
                    candidate = json.load(response)
                weather_code(candidate, time.time(), config.sunset_seconds)
                data, last_success = candidate, time.monotonic()
                state.set_hardware("weather", "ready", config.city)
            except Exception as exc:
                data = None  # Usar la base de respaldo hasta recuperar la API.
                # No registrar URL ni excepción completa: pueden contener la API key.
                log.warning("No se pudo actualizar el clima (%s)", type(exc).__name__)
                state.set_hardware("weather", "error", "No se pudo actualizar el clima")
            next_fetch = time.monotonic() + config.poll_seconds
        if data and time.monotonic() - last_success < config.stale_seconds:
            state.set_weather(weather_code(data, time.time(), config.sunset_seconds))
        else:
            state.set_weather(None)
        stop.wait(1)
