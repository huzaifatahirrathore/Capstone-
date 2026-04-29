from flask import Flask, request, jsonify, send_file
from ultralytics import YOLO
import cv2
import numpy as np
import os
from compare import compare 
app = Flask(__name__)

model = YOLO("best.pt")

@app.route('/detect', methods=['POST'])
def detect():
    file = request.files['image']

    img_bytes = file.read()
    npimg = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    results = model(img, conf=0.05)

    detections = []

    for r in results:
        for box in r.boxes:
            detections.append({
                "class": int(box.cls[0]),
                "confidence": float(box.conf[0]),
                "bbox": box.xyxy[0].tolist()
            })

    return jsonify({"detections": detections})

@app.route('/compare', methods=['POST'])
def compare_api():
    try:
        before = request.files['before']
        after = request.files['after']

        before_path = "before.jpg"
        after_path = "after.jpg"

        before.save(before_path)
        after.save(after_path)

        compare(before_path, after_path)

        output_path = "results/compare_before_vs_after.jpg"

        if not os.path.exists(output_path):
            return {"error": "Output image not found"}, 500

        return send_file(output_path, mimetype='image/jpeg')

    except Exception as e:
        print("COMPARE ERROR:", e)
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(port=5000)