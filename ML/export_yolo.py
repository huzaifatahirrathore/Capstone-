from ultralytics import YOLO

model = YOLO("yolo11n.pt")  # downloads ~5MB weights automatically

model.export(
    format="onnx",
    imgsz=320,
    opset=19,
    simplify=True,   # runs onnxslim to clean up the graph
    dynamic=False,   # fixed batch size = 1, required for ONNX Runtime Android
    half=False,      # keep float32 — ONNX Runtime Android handles quantization
)