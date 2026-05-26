"""
refine_masks_with_sam.py — Use SAM to refine YOLO bboxes into precise canopy masks.

For each training image:
  1. Run YOLO to detect tree bboxes
  2. For each bbox, prompt SAM with the box bounds
  3. SAM returns a precise canopy mask (not just the bbox rectangle)
  4. Convert mask contours to polygon format
  5. Save as YOLO-seg labels (dataset/labels_seg/)

This produces pixel-accurate instance masks for training YOLO-seg.
Overhead: ~1-2 hours on RTX 3060 for 2500 images (one-time cost).
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

try:
    from segment_anything import sam_model_registry, SamPredictor
except ImportError:
    print("Error: segment_anything not installed. Run: pip install segment-anything")
    sys.exit(1)


MODEL_PATH = "runs/detect/runs/tree_detect/yolo26m_trees-8/weights/best.pt"
SAM_MODEL_TYPE = "vit_b"
SAM_CHECKPOINT = "sam_vit_b_01ec64.pth"

INFER_IMGSZ = 1280
INFER_IOU = 0.6


def download_sam_checkpoint():
    """Download SAM checkpoint if not present."""
    checkpoint_path = Path(SAM_CHECKPOINT)
    if checkpoint_path.exists():
        return str(checkpoint_path)

    print(f"Downloading SAM checkpoint ({SAM_MODEL_TYPE})...")
    import urllib.request
    url = f"https://dl.fbaipublicfiles.com/segment_anything/{SAM_CHECKPOINT}"
    try:
        urllib.request.urlretrieve(url, SAM_CHECKPOINT)
        print(f"✅ Downloaded to {SAM_CHECKPOINT}")
        return str(checkpoint_path)
    except Exception as e:
        print(f"❌ Failed to download SAM checkpoint: {e}")
        print(f"   Manual download: {url}")
        sys.exit(1)


def mask_to_polygon(mask: np.ndarray) -> list:
    """
    Convert a binary mask to a list of normalized polygon coordinates.

    Returns: [x1_norm, y1_norm, x2_norm, y2_norm, ...] or [] if no contour found
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []

    # Use the largest contour
    contour = max(contours, key=cv2.contourArea)
    contour = contour.reshape(-1, 2).astype(np.float32)

    # Approximate contour to reduce points (optional, but speeds up training)
    epsilon = 0.01 * cv2.arcLength(contour, True)
    contour = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)

    # Normalize to [0, 1]
    h, w = mask.shape
    contour[:, 0] /= w
    contour[:, 1] /= h
    polygon = contour.flatten().tolist()

    return polygon


def refine_dataset():
    """Process all training images: YOLO detect → SAM refine → save labels."""

    print(f"Loading YOLO model: {MODEL_PATH}")
    yolo = YOLO(MODEL_PATH)

    print(f"Initializing SAM model ({SAM_MODEL_TYPE})...")
    checkpoint = download_sam_checkpoint()
    sam = sam_model_registry[SAM_MODEL_TYPE](checkpoint=checkpoint)
    sam.to(device="cuda")
    predictor = SamPredictor(sam)

    dataset_dir = Path("dataset")
    images_dir = dataset_dir / "images"
    labels_out = dataset_dir / "labels_seg"
    labels_out.mkdir(parents=True, exist_ok=True)

    total_masks = 0
    total_images = 0

    for split in ("train", "val", "test"):
        split_dir = images_dir / split
        if not split_dir.exists():
            continue

        (labels_out / split).mkdir(parents=True, exist_ok=True)

        image_files = sorted(split_dir.glob("*.*"))
        for i, img_path in enumerate(image_files, 1):
            if img_path.suffix.lower() not in (".jpg", ".png", ".jpeg"):
                continue

            print(f"[{split:5s}] {i:4d}/{len(image_files)}  {img_path.name:30s}", end=" ")

            img = cv2.imread(str(img_path))
            if img is None:
                print("❌ Could not read image")
                continue

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w = img.shape[:2]

            # YOLO detection
            results = yolo(str(img_path), conf=0.25, iou=0.6, imgsz=INFER_IMGSZ,
                          verbose=False)[0]

            if len(results.boxes) == 0:
                print("⊘ no detections")
                total_images += 1
                continue

            # Set image for SAM (done once per image for efficiency)
            predictor.set_image(img_rgb)

            polygons = []
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                # SAM bbox prompt format: [x1, y1, x2, y2]
                box_prompt = np.array([x1, y1, x2, y2])

                # SAM inference
                try:
                    masks, _, _ = predictor.predict(box=box_prompt, multimask_output=False)
                    mask = masks[0]  # Shape: (H, W)
                except Exception as e:
                    print(f"⚠ SAM failed: {e}")
                    continue

                # Convert mask to polygon
                polygon = mask_to_polygon((mask * 255).astype(np.uint8))
                if polygon:
                    polygons.append((0, polygon))  # class_id=0 (tree)

            # Save as YOLO-seg label
            label_file = labels_out / split / (img_path.stem + ".txt")

            with open(label_file, "w") as f:
                for cls_id, polygon in polygons:
                    line = str(cls_id) + " " + " ".join(f"{v:.6f}" for v in polygon)
                    f.write(line + "\n")

            total_masks += len(polygons)
            total_images += 1
            print(f"✅ {len(polygons)} masks")

    print()
    print("=" * 70)
    print(f"✅ Processing complete!")
    print(f"   Total images processed: {total_images}")
    print(f"   Total masks refined:    {total_masks}")
    print(f"   Output directory:       {labels_out}")
    print()
    print("Next steps:")
    print("  1. Create dataset_seg.yaml (same as dataset.yaml but point to labels_seg)")
    print("  2. Train: yolo segment train model=yolov8m-seg.pt data=dataset_seg.yaml")
    print("            epochs=100 imgsz=960 batch=2 device=0")


if __name__ == "__main__":
    refine_dataset()
