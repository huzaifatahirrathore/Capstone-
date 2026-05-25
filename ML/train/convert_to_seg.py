"""
convert_to_seg.py — Convert YOLO bbox labels to YOLO instance segmentation format.

Reads: dataset/labels/{train,val,test}/*.txt  (YOLO detection format)
Writes: dataset/labels_seg/{train,val,test}/*.txt  (YOLO segmentation format)

Each bbox is converted to a 4-point polygon (rectangle corners in pixel coords).
"""

import json
from pathlib import Path
from collections import defaultdict


def convert_bbox_to_polygon(cx_norm, cy_norm, w_norm, h_norm, img_w, img_h):
    """
    Convert YOLO normalized bbox → pixel polygon (4 corners).

    Returns list of 8 values: [x1, y1, x2, y2, x3, y3, x4, y4]
    (top-left, top-right, bottom-right, bottom-left)
    """
    cx = cx_norm * img_w
    cy = cy_norm * img_h
    w = w_norm * img_w
    h = h_norm * img_h

    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy - h / 2
    x3 = cx + w / 2
    y3 = cy + h / 2
    x4 = cx - w / 2
    y4 = cy + h / 2

    return [x1, y1, x2, y2, x3, y3, x4, y4]


def main():
    dataset_dir = Path("dataset")
    labels_in  = dataset_dir / "labels"
    labels_out = dataset_dir / "labels_seg"

    # Create output structure
    for split in ("train", "val", "test"):
        (labels_out / split).mkdir(parents=True, exist_ok=True)

    # Load image dimensions from dataset.yaml
    yaml_path = dataset_dir / "dataset.yaml"
    if not yaml_path.exists():
        print("Error: dataset.yaml not found")
        return

    with open(yaml_path) as f:
        yaml_text = f.read()

    # Parse the images path from yaml to infer image dimensions
    # (We'll read actual image dimensions from disk when processing)
    images_dir = dataset_dir / "images"

    processed = 0
    for split in ("train", "val", "test"):
        split_dir = labels_in / split
        if not split_dir.exists():
            continue

        for label_file in sorted(split_dir.glob("*.txt")):
            # Find corresponding image to get dimensions
            img_name = label_file.stem
            img_path = None
            for ext in (".jpg", ".png", ".jpeg"):
                candidate = images_dir / split / (img_name + ext)
                if candidate.exists():
                    img_path = candidate
                    break

            if img_path is None:
                print(f"Warning: no image found for {label_file.stem}")
                continue

            import cv2
            img = cv2.imread(str(img_path))
            if img is None:
                print(f"Warning: could not read image {img_path}")
                continue
            img_h, img_w = img.shape[:2]

            # Read bbox labels
            lines = label_file.read_text().strip().split('\n')
            if not lines or lines[0] == '':
                lines = []

            # Convert to polygon format
            out_lines = []
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                cls_id = parts[0]
                cx_norm = float(parts[1])
                cy_norm = float(parts[2])
                w_norm  = float(parts[3])
                h_norm  = float(parts[4])

                polygon = convert_bbox_to_polygon(cx_norm, cy_norm, w_norm, h_norm,
                                                   img_w, img_h)

                # YOLO-seg format: class_id x1 y1 x2 y2 ... xn yn (normalized coords)
                polygon_norm = [c / (img_w if i % 2 == 0 else img_h)
                                for i, c in enumerate(polygon)]
                out_line = cls_id + ' ' + ' '.join(f"{v:.6f}" for v in polygon_norm)
                out_lines.append(out_line)

            # Write output
            out_file = labels_out / split / label_file.name
            out_file.write_text('\n'.join(out_lines) + ('\n' if out_lines else ''))
            processed += 1

    print(f"✅ Converted {processed} label files to segmentation format")
    print(f"   Output: {labels_out}")
    print()
    print("Next steps:")
    print("  1. Update dataset.yaml to point to labels_seg instead of labels")
    print("  2. Train: yolo segment train model=yolov8m-seg.pt data=dataset.yaml epochs=100 imgsz=960")


if __name__ == "__main__":
    main()
