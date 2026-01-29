from ultralytics import YOLO
import cv2
import write_xml as w

# Cargar el modelo YOLO
model = YOLO("C:\\Users\\BitsandAtoms\\Proyectos\\iaMunecos\\prFigurasIA\\yoloFiguritasv2.pt")  # AsegÃºrate de usar la ruta correcta de tu archivo .pt

# Abrir la cÃ¡mara
cap = cv2.VideoCapture(0)
while cap.isOpened():
    success, image = cap.read()  # Captura un frame de la cÃ¡mara
    if not success:
        #print("Ignorando frame vacÃ­o de la cÃ¡mara.")
        continue

    # Realizar la detecciÃ³n con el modelo YOLO
    results = model.predict(image, conf=0.7)  # Realiza la predicciÃ³n
    r = results[0]
    
    # Guardamos la info de la taza del frame
    for box in r.boxes:
        cls_id = int(box.cls[0])       # id de clase
        conf   = float(box.conf[0])    # confianza
        name   = r.names[cls_id]       # nombre de clase, segÃºn tu data.yaml

        # #filtrar por confianza Modelo v3+
        # if conf < 0.8:
        #     continue
        # if name == "Alfred Pennyworth":
        #     w.writeValor("A")
        # if name == "Batgirl":
        #     w.writeValor("G")
        # if name == "Bruce Wayne":
        #     w.writeValor("B")
        # if name == "Catwoman":
        #     w.writeValor("C")
        # if name == "Cyborg":
        #     w.writeValor("Y")
        # if name == "Flash":
        #     w.writeValor("F")
        # if name == "Harley Quien":
        #     w.writeValor("H")
        # if name == "Joker":
        #     w.writeValor("J")
        # if name == "Jor-el":
        #     w.writeValor("S")
        # if name == "Wonder Woman":
        #     w.writeValor("W")

        #filtrar por confianza modelo v2
        if conf < 0.8:
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
            
            
    # `results` es una lista de resultados, acceder al primer resultado
    # La imagen procesada con las anotaciones se obtiene desde `results[0].plot()`
    annotated_image = r.plot()  # Devuelve la imagen con las anotaciones

    # Mostrar la imagen con las detecciones
    cv2.imshow("Detecciones YOLO", annotated_image)

    # Salir del bucle si se presiona la tecla 'q'
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# Liberar la cÃ¡mara y cerrar todas las ventanas de OpenCV
cap.release()
cv2.destroyAllWindows()