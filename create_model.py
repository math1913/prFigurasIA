from ultralytics import YOLO

model = YOLO("yolo26m.pt")

model.train(data="figuritas_dataset.yaml", epochs=20, batch=12)