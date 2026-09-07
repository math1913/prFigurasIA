"""Compatibilidad de importación: el clima ahora se inicia desde main.py."""

from display_app.weather import run_weather, weather_code

if __name__ == "__main__":
    raise SystemExit("El clima está integrado. Ejecuta: python main.py")
