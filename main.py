from ultralytics import YOLO
import cv2
import write_xml as w

# Cargar el modelo YOLO
model = YOLO('prFigurasIA/yoloFiguritasv3.pt')  # Asegúrate de usar la ruta correcta de tu archivo .pt

# Abrir la cámara
cap = cv2.VideoCapture(0)
while cap.isOpened():
    success, image = cap.read()  # Captura un frame de la cámara
    if not success:
        #print("Ignorando frame vacío de la cámara.")
        continue

    # Realizar la detección con el modelo YOLO
    results = model.predict(image, conf=0.7)  # Realiza la predicción
    r = results[0]
    
    # Guardamos la info de la taza del frame
    for box in r.boxes:
        cls_id = int(box.cls[0])       # id de clase
        conf   = float(box.conf[0])    # confianza
        name   = r.names[cls_id]       # nombre de clase, según tu data.yaml

        #filtrar por confianza
        if conf < 0.8:
            continue
        if name == "Alfred Pennyworth":
            w.writeValor("A")
        if name == "Batgirl":
            w.writeValor("G")
        if name == "Bruce Wayne":
            w.writeValor("B")
        if name == "Catwoman":
            w.writeValor("C")
        if name == "Cyborg":
            w.writeValor("Y")
        if name == "Flash":
            w.writeValor("F")
        if name == "Harley Quien":
            w.writeValor("H")
        if name == "Joker":
            w.writeValor("J")
        if name == "Jor-el":
            w.writeValor("S")
        if name == "Wonder Woman":
            w.writeValor("W")
            
            
    # `results` es una lista de resultados, acceder al primer resultado
    # La imagen procesada con las anotaciones se obtiene desde `results[0].plot()`
    annotated_image = r.plot()  # Devuelve la imagen con las anotaciones

    # Mostrar la imagen con las detecciones
    cv2.imshow("Detecciones YOLO", annotated_image)

    # Salir del bucle si se presiona la tecla 'q'
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# Liberar la cámara y cerrar todas las ventanas de OpenCV
cap.release()
cv2.destroyAllWindows()
