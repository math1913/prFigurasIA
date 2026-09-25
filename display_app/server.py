from contextlib import asynccontextmanager
import asyncio
import logging
from pathlib import Path
import threading
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import ROOT, WEATHER_CODES, load_settings
from .figures import run_figures
from .barcode import handle_scan, load_mapping, run_barcode
from .nfc import run_nfc
from .state import DisplayState
from .weather import run_weather

ChannelName = Literal["figuras", "nfc"]
log = logging.getLogger(__name__)


class Trigger(BaseModel):
    key: str


class Completion(BaseModel):
    event_id: str


def create_app(config_path: Path | None = None, demo=False, settings=None):
    settings = settings or load_settings(config_path)
    state = DisplayState(settings)

    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        workers = []
        for channel, config, target in [
            ("figuras", settings.figures, run_figures),
            ("barcode", settings.barcode, run_barcode),
            ("nfc", settings.nfc, run_nfc),
            ("weather", settings.weather, run_weather),
        ]:
            if demo or not config.enabled:
                state.set_hardware(channel, "demo" if demo else "disabled",
                                   "Simulación" if demo else "Desactivado en config.json")
            else:
                worker = threading.Thread(target=target, args=(state, stop),
                                          name=channel, daemon=True)
                worker.start()
                workers.append(worker)
        try:
            yield
        finally:
            stop.set()
            for worker in workers:
                await asyncio.to_thread(worker.join, 12)
                if worker.is_alive():
                    log.warning("El dispositivo %s no terminó dentro de 12 segundos", worker.name)

    app = FastAPI(title="BigBang · Figuras y NFC", lifespan=lifespan)
    app.state.displays = state

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/figuras", include_in_schema=False)
    def figures_page():
        return FileResponse(ROOT / "web" / "figuras.html")

    @app.get("/nfc", include_in_schema=False)
    def nfc_page():
        return FileResponse(ROOT / "web" / "nfc.html")

    @app.get("/overlay", include_in_schema=False)
    def overlay_page():
        return FileResponse(ROOT / "web" / "overlay.html")

    @app.get("/api/state/{channel}")
    def get_state(channel: ChannelName, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return state.snapshot(channel)

    @app.post("/api/complete/{channel}")
    def complete(channel: ChannelName, event: Completion):
        return {"accepted": state.complete(channel, event.event_id)}

    @app.get("/api/status")
    def get_status(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"demo": demo, **state.health(),
                "events": {name: {key: video.title for key, video in config.events.items()}
                           for name, config in settings.channels.items()},
                "weather_videos": {key: video.title for key, video in settings.weather.videos.items()}}

    @app.get("/api/barcodes")
    def get_barcodes():
        try:
            return load_mapping(ROOT / settings.barcode.mapping_file)
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "No se pudo leer barcode_id.json") from exc

    @app.post("/api/demo/barcode")
    def simulate_barcode(event: Trigger):
        if not demo:
            raise HTTPException(403, "Inicia con --demo para simular acciones")
        try:
            accepted = handle_scan(state, event.key)
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "No se pudo leer barcode_id.json") from exc
        if not accepted:
            raise HTTPException(404, "Código desconocido o sin contenido configurado")
        return {"accepted": True}

    @app.get("/objetos")
    def get_objects(response: Response):
        response.headers["Cache-Control"] = "no-store"
        if state.health()["hardware"]["nfc"]["status"] not in {"ready", "demo"}:
            raise HTTPException(503, "Lector NFC no disponible")
        return state.objects()

    @app.post("/api/demo/weather")
    def simulate_weather(event: Trigger):
        if not demo:
            raise HTTPException(403, "Inicia con --demo para simular acciones")
        if event.key not in WEATHER_CODES:
            raise HTTPException(404, "Clima desconocido")
        state.set_weather(event.key)
        return {"accepted": True}

    @app.post("/api/demo/{channel}")
    def simulate(channel: ChannelName, event: Trigger):
        if not demo:
            raise HTTPException(403, "Inicia con --demo para simular acciones")
        if event.key not in settings.channels[channel].events:
            raise HTTPException(404, "Contenido desconocido")
        state.trigger(channel, event.key)
        return {"accepted": True}

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
    app.mount("/media", StaticFiles(directory=ROOT / "media"), name="media")
    return app
