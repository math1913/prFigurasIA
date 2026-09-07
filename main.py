from ultralytics import YOLO
import cv2
import write_xml as w

MODEL_PATH = r"C:\Users\Admira\Documents\prFiguras\prFigurasIA\yoloFiguritasv2.pt"
CAM_INDEX = 0


# ---------------------------
# ROI en píxeles (x1, y1) -> (x2, y2)
ROI_X1, ROI_Y1 = 150, 00
ROI_X2, ROI_Y2 = 450, 640
CONF_ADMIRA = 0.9 # Confianza necesaria para enviarle a admira
CONF_MOSTRAR = 0.6 # Confianza necesaria para mostrarse en pantalla
# ---------------------------


# resolucion de captura
CAP_W, CAP_H = 640, 640 
FLIP   = 1


model = YOLO(MODEL_PATH)

cap = cv2.VideoCapture(CAM_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAP_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAP_H)

while cap.isOpened():
    success, image = cap.read()
    if not success:
        continue

    h, w_img = image.shape[:2]

    # Asegurar ROI dentro de la imagen
    x1 = max(0, min(ROI_X1, w_img - 1))
    y1 = max(0, min(ROI_Y1, h - 1))
    x2 = max(0, min(ROI_X2, w_img))
    y2 = max(0, min(ROI_Y2, h))

    if x2 <= x1 or y2 <= y1:
        # ROI inválido
        cv2.imshow("Detecciones YOLO", image)
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break
        continue

    if FLIP in (0, 1, -2):
        if FLIP == -2:
            image = cv2.flip(image, -1)
        else:
            image = cv2.flip(image, FLIP)
    roi = image[y1:y2, x1:x2]

    # Predicción SOLO en el ROI
    results = model.predict(roi, conf=CONF_MOSTRAR)  # tu conf base
    r = results[0]

    # Filtrado y escritura
    for box in r.boxes:
        cls_id = int(box.cls[0])
        conf   = float(box.conf[0])
        name   = r.names[cls_id]

        if conf < CONF_ADMIRA:
            continue
        if name == "Alfred":
            w.writeValor("A")
        if name == "Batgirl":
            w.writeValor("G")
        if name == "Bruce":
            w.writeValor("B")
        if name == "Catwoman":
            w.writeValor("C")
        if name == "Cyborg":
            w.writeValor("Y")
        if name == "Flash":
            w.writeValor("F")
        if name == "Harley":
            w.writeValor("H")
        if name == "Joker":
            w.writeValor("J")
        if name == "Superman":
            w.writeValor("S")
        if name == "WonderWoman":
            w.writeValor("W")

    # 4) Visualización: dibujar detecciones en el ROI y reinsertarlas en el frame completo
    annotated_roi = r.plot()
    annotated_full = image.copy()
    annotated_full[y1:y2, x1:x2] = annotated_roi

    # opcional: dibujar el rectángulo del ROI para verlo claro
    cv2.rectangle(annotated_full, (x1, y1), (x2, y2), (0, 255, 0), 2)

    cv2.imshow("Detecciones YOLO", annotated_full)

    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()