import logging

from .config import ROOT
from .state import FigureGate

log = logging.getLogger(__name__)


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
    while not stop.is_set():
        capture = None
        try:
            capture = cv2.VideoCapture(config.camera)
            if not capture.isOpened():
                raise RuntimeError(f"No se puede abrir la cámara {config.camera}")
            state.set_hardware("figuras", "ready", f"Cámara {config.camera}")
            while not stop.is_set():
                success, frame = capture.read()
                if not success:
                    raise RuntimeError("No se reciben imágenes de la cámara")
                result = model.predict(frame, conf=config.confidence, verbose=False)[0]
                detections = []
                for box in result.boxes:
                    key = config.labels.get(result.names[int(box.cls[0])])
                    confidence = float(box.conf[0])
                    if key and confidence >= config.confidence:
                        detections.append((key, confidence))
                if config.repeat_while_present and state.is_idle("figuras"):
                    gate.fired.clear()
                key = gate.update(detections)
                if key:
                    state.trigger("figuras", key)
                if config.preview:
                    cv2.imshow("Detecciones YOLO", result.plot())
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        state.set_hardware("figuras", "disabled", "Detector detenido con Q")
                        return
                stop.wait(0.01)
        except Exception as exc:
            log.exception("Error de cámara; reintentando")
            state.set_hardware("figuras", "error", str(exc))
            gate.reset_visibility()
            stop.wait(2)
        finally:
            if capture is not None:
                capture.release()
            if config.preview:
                cv2.destroyAllWindows()
