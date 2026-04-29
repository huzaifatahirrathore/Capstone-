import argparse
import sys
from pathlib import Path
from ultralytics import YOLO
from flask import send_file
import os
from compare import compare 

MODEL_PATH = "best.pt"


def detect(image_path: str, conf: float = 0.25, save: bool = True):
    """Run tree detection on a single image."""
    if not Path(image_path).exists():
        print(f"Error: image not found — {image_path}")
        sys.exit(1)

    model = YOLO(MODEL_PATH)
    results = model(image_path, conf=conf, iou=0.7)[0]

    print(f"\nDetected {len(results.boxes)} tree(s) in: {image_path}\n")
    for i, box in enumerate(results.boxes, 1):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        confidence = box.conf[0].item()
        cls_id = int(box.cls[0].item())
        cls_name = model.names[cls_id]
        print(f"  [{i}] {cls_name}  conf={confidence:.2f}  box=({x1:.0f}, {y1:.0f}, {x2:.0f}, {y2:.0f})")

    if save:
        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        annotated = results.plot()

        import cv2
        out_path = out_dir / f"detected_{Path(image_path).name}"
        cv2.imwrite(str(out_path), annotated)
        print(f"\nAnnotated image saved to: {out_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect trees in an image using the trained YOLO model.")
    parser.add_argument("image", help="Path to the input image")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (default: 0.25)")
    parser.add_argument("--no-save", action="store_true", help="Don't save the annotated image")
    args = parser.parse_args()

    detect(args.image, conf=args.conf, save=not args.no_save)