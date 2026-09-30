"""Detector de figuras como el script antiguo (main.py de la rama main).

Se voltea la imagen, se detecta solo dentro de la zona (el ROI) y se abre la ventana
«Detecciones YOLO» con la imagen completa, las detecciones y la zona recuadrada en verde,
para volver a colocar la cámara si se mueve.
"""

import logging
import os

from .config import ROOT
from .state import FigureGate

log = logging.getLogger(__name__)
WINDOW = "Detecciones YOLO"
ZONE_COLOR = (0, 255, 0)


def crop(frame, zone):
    """La zona (x1, y1, x2, y2) ajustada a la imagen; sin zona o fuera de ella, toda la imagen."""
    height, width = frame.shape[:2]
    if not zone:
        return 0, 0, width, height
    x1, y1, x2, y2 = zone
    x1, x2 = max(0, min(x1, width)), max(0, min(x2, width))
    y1, y2 = max(0, min(y1, height)), max(0, min(y2, height))
    if x2 <= x1 or y2 <= y1:
        return 0, 0, width, height
    return x1, y1, x2, y2


def annotate(cv2, frame, result, box, zone):
    """La imagen completa con las detecciones dibujadas en la zona y la zona recuadrada en verde."""
    x1, y1, x2, y2 = box
    image = frame.copy()
    image[y1:y2, x1:x2] = result.plot()
    if zone:
        cv2.rectangle(image, (x1, y1), (x2, y2), ZONE_COLOR, 2)
    return image


def show_normal(title):
    """La aplicación arranca minimizada (acceso directo de Inicio) y Windows abriría la ventana minimizada."""
    if os.name != "nt":
        return
    import ctypes
    window = ctypes.windll.user32.FindWindowW(None, title)
    if window:
        ctypes.windll.user32.ShowWindow(window, 1)  # SW_SHOWNORMAL


def run_figures(state, stop):
    config = state.settings.figures
    try:
        import cv2
        from ultralytics import YOLO

        model_path = ROOT / config.model
        if not model_path.is_file():
            raise FileNotFoundError(f"No existe el modelo: {model_path}")
        model = YOLO(str(model_path))
    except Exception as exc:
        log.exception("No se pudo cargar el detector de figuras")
        state.set_hardware("figuras", "error", str(exc))
        return

    gate = FigureGate(config.stable_seconds, config.absence_seconds,
                      cooldown_seconds=config.cooldown_seconds)
    # Se detecta desde el umbral de la ventana; solo activan el vídeo las que llegan a confidence.
    predict_confidence = min(config.display_confidence, config.confidence)
    window = config.preview
    restored = False
    while not stop.is_set():
        capture = None
        try:
            capture = cv2.VideoCapture(config.camera)
            if not capture.isOpened():
                raise RuntimeError(f"No se puede abrir la cámara {config.camera}")
            if config.capture_size:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.capture_size[0])
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.capture_size[1])
            state.set_hardware("figuras", "ready", f"Cámara {config.camera}")
            while not stop.is_set():
                success, frame = capture.read()
                if not success:
                    raise RuntimeError("No se reciben imágenes de la cámara")
                if config.flip is not None:
                    frame = cv2.flip(frame, config.flip)
                box = crop(frame, config.zone)
                x1, y1, x2, y2 = box
                result = model.predict(frame[y1:y2, x1:x2], conf=predict_confidence, verbose=False)[0]
                detections = []
                for detected in result.boxes:
                    key = config.labels.get(result.names[int(detected.cls[0])])
                    confidence = float(detected.conf[0])
                    if key and confidence >= config.confidence:
                        detections.append((key, confidence))
                if config.repeat_while_present and state.is_idle("figuras"):
                    gate.fired.clear()
                key = gate.update(detections)
                if key:
                    state.trigger("figuras", key)
                if window:
                    cv2.imshow(WINDOW, annotate(cv2, frame, result, box, config.zone))
                    if not restored:
                        show_normal(WINDOW)
                        restored = True
                    # Q cierra la ventana; a diferencia del script antiguo, la detección sigue.
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        window = False
                        cv2.destroyAllWindows()
                stop.wait(0.01)
        except Exception as exc:
            log.exception("Error de cámara; reintentando")
            state.set_hardware("figuras", "error", str(exc))
            gate.reset_visibility()
            stop.wait(2)
        finally:
            if capture is not None:
                capture.release()
    if window:
        cv2.destroyAllWindows()
