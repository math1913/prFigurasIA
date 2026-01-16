from ultralytics import YOLO

model = YOLO("yolo11n.pt")

model.train(data="harley_dataset.yaml", epochs=20)