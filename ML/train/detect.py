import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

MODEL_PATH = "runs/detect/runs/tree_detect/yolo26m_trees-8/weights/best.pt"

# Single-pass inference at 1280 — higher than training (960), fits on 6 GB VRAM at inference
INFER_IMGSZ   = 1280
INFER_IOU     = 0.6

# Tiling is only worth it for very large images (e.g. drone maps).
# For typical photos (≤1920 px), a single high-res pass is better.
TILE_SIZE      = 640
TILE_OVERLAP   = 0.2
TILE_THRESHOLD = 1920   # tile only when image exceeds this in either dimension


def _draw_boxes(img: np.ndarray, boxes: list) -> np.ndarray:
    annotated = img.copy()
    for b in boxes:
        x1, y1, x2, y2, bc, _ = b
        cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        label = f"tree {bc:.2f}"
        cv2.putText(annotated, label, (int(x1), max(int(y1) - 5, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(annotated, label, (int(x1), max(int(y1) - 5, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
    return annotated


def _tile_and_predict(model: YOLO, image_path: str, conf: float) -> tuple:
    """
    For normal-sized images (≤ TILE_THRESHOLD): single pass at INFER_IMGSZ.
    For very large images (drone maps, etc.): overlapping 640×640 tiles + cross-tile NMS.

    Returns (boxes, annotated_bgr)
    boxes : list of [x1, y1, x2, y2, confidence, class_id]
    """
    img = cv2.imread(image_path)
    if img is None:
        return [], np.zeros((100, 100, 3), dtype=np.uint8)

    H, W = img.shape[:2]

    # ── Single-pass path ──────────────────────────────────────────────────────
    if W <= TILE_THRESHOLD and H <= TILE_THRESHOLD:
        res = model(image_path, conf=conf, iou=INFER_IOU,
                    imgsz=INFER_IMGSZ, verbose=False)[0]
        boxes = []
        for box in res.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            boxes.append([x1, y1, x2, y2, box.conf[0].item(), int(box.cls[0].item())])
        return boxes, _draw_boxes(img, boxes)

    # ── Tiled path (large images only) ───────────────────────────────────────
    step = max(1, int(TILE_SIZE * (1 - TILE_OVERLAP)))
    tmp_tile = str(Path("tmp") / "_tile_detect.jpg")
    Path("tmp").mkdir(exist_ok=True)

    raw = []
    for ty in range(0, H, step):
        for tx in range(0, W, step):
            tx1 = max(0, min(tx, W - TILE_SIZE)) if W >= TILE_SIZE else 0
            ty1 = max(0, min(ty, H - TILE_SIZE)) if H >= TILE_SIZE else 0
            tx2 = min(tx1 + TILE_SIZE, W)
            ty2 = min(ty1 + TILE_SIZE, H)

            tile = img[ty1:ty2, tx1:tx2]
            cv2.imwrite(tmp_tile, tile)

            res = model(tmp_tile, conf=conf, iou=INFER_IOU, verbose=False)[0]
            for box in res.boxes:
                bx1, by1, bx2, by2 = box.xyxy[0].tolist()
                raw.append([bx1 + tx1, by1 + ty1, bx2 + tx1, by2 + ty1,
                             box.conf[0].item(), int(box.cls[0].item())])

    if not raw:
        return [], img.copy()

    xywh   = [[b[0], b[1], b[2] - b[0], b[3] - b[1]] for b in raw]
    scores = [b[4] for b in raw]
    idx    = cv2.dnn.NMSBoxes(xywh, scores, conf, INFER_IOU)
    final  = [raw[i] for i in idx.flatten()] if len(idx) > 0 else []

    return final, _draw_boxes(img, final)


def detect(image_path: str, conf: float = 0.25, save: bool = True):
    """Run tree detection on a single image."""
    if not Path(image_path).exists():
        print(f"Error: image not found — {image_path}")
        sys.exit(1)

    model = YOLO(MODEL_PATH)
    boxes, annotated = _tile_and_predict(model, image_path, conf=conf)

    print(f"\nDetected {len(boxes)} tree(s) in: {image_path}\n")
    for i, b in enumerate(boxes, 1):
        x1, y1, x2, y2, bc, cls_id = b
        print(f"  [{i}] {model.names[cls_id]}  conf={bc:.2f}"
              f"  box=({x1:.0f}, {y1:.0f}, {x2:.0f}, {y2:.0f})")

    if save:
        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"detected_{Path(image_path).name}"
        cv2.imwrite(str(out_path), annotated)
        print(f"\nAnnotated image saved to: {out_path}")

    return boxes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Detect trees in an image using the trained YOLO model."
    )
    parser.add_argument("image", help="Path to the input image")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Confidence threshold (default: 0.25)")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't save the annotated image")
    args = parser.parse_args()

    detect(args.image, conf=args.conf, save=not args.no_save)
