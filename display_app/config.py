import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parent.parent
WEATHER_CODES = {"DL", "DD", "DN", "A", "NL", "ND", "NN"}
# cover llena la pantalla recortando lo que sobra, contain muestra el vídeo entero con bandas y fill lo estira.
Fit = Literal["contain", "cover", "fill"]


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Video(SettingsModel):
    title: str
    src: str | None = None
    muted: bool = True
    fit: Fit | None = None  # Sustituye al fit de su pantalla solo para este vídeo.

    @model_validator(mode="after")
    def validate_source(self):
        if self.src and (not self.src.startswith("/media/") or ".." in self.src):
            raise ValueError("src debe ser una ruta local /media/...")
        return self


class Channel(SettingsModel):
    # Solo es una protección para vídeos dañados o pantallas desconectadas.
    max_event_seconds: float = Field(default=3600, gt=0, le=86400)
    placeholder_seconds: float = Field(default=5, gt=0, le=3600)
    fit: Fit = "cover"
    # El sonido sale del PC (/audio/<canal>, en un navegador sin ventana) y la pantalla va en silencio.
    audio_on_pc: bool = False
    # Retrasa el sonido del PC para compensar lo que tarda la pantalla en mostrar la imagen.
    audio_delay_ms: int = Field(default=0, ge=-2000, le=2000)
    # Paso por negro al cambiar de vídeo: la mitad se va y la mitad vuelve. Donde salga el
    # sonido, baja y sube con él. 0 deja el cambio instantáneo.
    fade_ms: int = Field(default=0, ge=0, le=5000)
    base: Video
    events: dict[str, Video]


class Figures(SettingsModel):
    enabled: bool = True
    model: str = "yoloFiguritasv2.pt"
    camera: int | str = 0
    # Como el script antiguo: la ventana muestra detecciones desde display_confidence (CONF_MOSTRAR)
    # y solo activan el vídeo las que llegan a confidence (CONF_ADMIRA).
    confidence: float = Field(default=0.9, gt=0, le=1)
    display_confidence: float = Field(default=0.6, gt=0, le=1)
    stable_seconds: float = Field(default=0.5, ge=0)
    absence_seconds: float = Field(default=1, gt=0)
    cooldown_seconds: float = Field(default=60, ge=60)
    repeat_while_present: bool = False
    # Ventana «Detecciones YOLO» con la cámara, las detecciones y la zona en verde.
    preview: bool = True
    # Resolución pedida a la cámara (ancho, alto); usa la más parecida que tenga.
    capture_size: tuple[int, int] | None = (640, 640)
    # Volteo con los códigos de OpenCV: 1 horizontal, 0 vertical, -1 ambos; null, sin volteo.
    flip: Literal[-1, 0, 1] | None = 1
    # Zona de detección (x1, y1, x2, y2) en píxeles de la imagen: solo se detecta dentro (ROI).
    # null detecta en toda la imagen.
    zone: tuple[int, int, int, int] | None = (150, 0, 450, 640)
    labels: dict[str, str]


class NFC(SettingsModel):
    enabled: bool = True
    aliases_file: str = "aliases.json"
    trigger: Literal["insert", "remove"] = "remove"
    monitored_objects: list[str] = ["Beatles", "Jackson", "Prince", "Superman"]
    # Pantallas sobre las que se superpone /overlay con los logos detectados.
    overlay_channels: list[Literal["figuras", "nfc"]] = ["nfc"]


class Barcode(SettingsModel):
    enabled: bool = True
    mapping_file: str = "barcode_id.json"
    port: str | None = None
    vid: int = Field(default=9969, ge=0, le=65535)
    pid: int = Field(default=34818, ge=0, le=65535)
    baudrate: int = Field(default=9600, gt=0)
    bytesize: Literal[5, 6, 7, 8] = 8
    parity: Literal["N", "E", "O", "M", "S"] = "N"
    stopbits: Literal[1, 1.5, 2] = 1
    timeout_seconds: float = Field(default=1, gt=0, le=5)


class Weather(SettingsModel):
    enabled: bool = True
    city: str = "Barcelona"
    api_key_env: str = "OPENWEATHER_API_KEY"
    poll_seconds: float = Field(default=300, ge=10)
    stale_seconds: float = Field(default=1800, ge=10)
    sunset_seconds: float = Field(default=3600, ge=0)
    base_channels: list[Literal["figuras", "nfc"]] = ["figuras"]
    videos: dict[str, Video]

    @model_validator(mode="after")
    def validate_codes(self):
        if set(self.videos) != WEATHER_CODES:
            raise ValueError("Configura los siete vídeos de clima: DL, DD, DN, A, NL, ND, NN")
        return self


class Audio(SettingsModel):
    enabled: bool = True
    browser: str | None = None  # Ruta de Chrome o Edge; sin valor se busca sola.


class Admira(SettingsModel):
    # Reiniciar Admira cuando el servidor ya contesta, si acaba de arrancar con el PC.
    enabled: bool = True
    launcher: str | None = None  # Acceso directo o ejecutable de Admira; sin valor se busca solo.


class Settings(SettingsModel):
    figures: Figures
    nfc: NFC = Field(default_factory=NFC)
    barcode: Barcode = Field(default_factory=Barcode)
    weather: Weather
    audio: Audio = Field(default_factory=Audio)
    admira: Admira = Field(default_factory=Admira)
    channels: dict[str, Channel]

    @model_validator(mode="after")
    def validate_channels(self):
        if set(self.channels) != {"figuras", "nfc"}:
            raise ValueError("Se necesitan exactamente los canales figuras y nfc")
        missing = set(self.figures.labels.values()) - self.channels["figuras"].events.keys()
        if missing:
            raise ValueError(f"Falta contenido para las figuras: {sorted(missing)}")
        return self


def load_settings(path: Path | None = None) -> Settings:
    with (path or ROOT / "config.json").open(encoding="utf-8-sig") as source:
        return Settings.model_validate(json.load(source))
