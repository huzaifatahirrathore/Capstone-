# coco_to_yolo.py
import json
import os
import shutil
import random
from pathlib import Path
from collections import defaultdict

# ─── CONFIG ───────────────────────────────────────────────────────────────────
COCO_ANNOTATIONS = "_annotations.coco.json"   # path to your .coco file
IMAGES_DIR       = "."                          # folder where all images live
OUTPUT_DIR       = "dataset"                    # will be created fresh
TRAIN_RATIO      = 0.80
VAL_RATIO        = 0.15
# TEST gets the remainder (0.05)
RANDOM_SEED      = 42
# ──────────────────────────────────────────────────────────────────────────────

random.seed(RANDOM_SEED)

def coco_bbox_to_yolo(bbox, img_w, img_h):
    """Convert COCO [x_min, y_min, width, height] → YOLO [cx, cy, w, h] normalized."""
    x_min, y_min, w, h = [float(v) for v in bbox]
    cx = (x_min + w / 2) / img_w
    cy = (y_min + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    # Clamp to [0, 1] to handle any annotation overflow
    cx, cy, nw, nh = (max(0, min(1, v)) for v in (cx, cy, nw, nh))
    return cx, cy, nw, nh

def convert_and_split():
    # Load COCO JSON
    with open(COCO_ANNOTATIONS, "r") as f:
        coco = json.load(f)

    # Build lookup maps
    images_info   = {img["id"]: img for img in coco["images"]}
    categories    = {cat["id"]: cat["name"] for cat in coco["categories"]}
    cat_id_to_yolo = {cid: i for i, cid in enumerate(sorted(categories.keys()))}

    # Group annotations by image
    anns_by_image = defaultdict(list)
    for ann in coco["annotations"]:
        anns_by_image[ann["image_id"]].append(ann)

    # Print dataset summary
    print(f"Found {len(images_info)} images, {len(coco['annotations'])} annotations")
    print(f"Categories: {categories}")

    # Create output directory structure
    splits = ["train", "val", "test"]
    for split in splits:
        Path(f"{OUTPUT_DIR}/images/{split}").mkdir(parents=True, exist_ok=True)
        Path(f"{OUTPUT_DIR}/labels/{split}").mkdir(parents=True, exist_ok=True)

    # Shuffle image IDs and split
    all_image_ids = list(images_info.keys())
    random.shuffle(all_image_ids)
    n = len(all_image_ids)
    n_train = int(n * TRAIN_RATIO)
    n_val   = int(n * VAL_RATIO)

    split_map = {}
    for i, img_id in enumerate(all_image_ids):
        if   i < n_train:           split_map[img_id] = "train"
        elif i < n_train + n_val:   split_map[img_id] = "val"
        else:                       split_map[img_id] = "test"

    # Convert and copy
    skipped = 0
    for img_id, info in images_info.items():
        split     = split_map[img_id]
        file_name = info["file_name"]
        img_w     = float(info["width"])
        img_h     = float(info["height"])

        src = Path(IMAGES_DIR) / file_name
        if not src.exists():
            print(f"  WARNING: image not found → {src}")
            skipped += 1
            continue

        # Copy image
        dst_img = Path(OUTPUT_DIR) / "images" / split / file_name
        shutil.copy2(src, dst_img)

        # Write YOLO label file
        dst_lbl = Path(OUTPUT_DIR) / "labels" / split / (Path(file_name).stem + ".txt")
        annotations = anns_by_image.get(img_id, [])

        with open(dst_lbl, "w") as f:
            for ann in annotations:
                # Skip crowd annotations
                if ann.get("iscrowd", 0):
                    continue
                yolo_cls = cat_id_to_yolo[ann["category_id"]]
                cx, cy, w, h = coco_bbox_to_yolo(ann["bbox"], img_w, img_h)
                # Skip degenerate boxes
                if w <= 0 or h <= 0:
                    continue
                f.write(f"{yolo_cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

    # Write dataset.yaml
    yaml_content = f"""path: {Path(OUTPUT_DIR).resolve()}
train: images/train
val: images/val
test: images/test

nc: {len(categories)}
names: {[categories[k] for k in sorted(categories.keys())]}
"""
    with open(f"{OUTPUT_DIR}/dataset.yaml", "w") as f:
        f.write(yaml_content)

    # Final report
    counts = defaultdict(int)
    for s in split_map.values():
        counts[s] += 1

    print("\n✅ Conversion complete!")
    print(f"   Train : {counts['train']} images")
    print(f"   Val   : {counts['val']} images")
    print(f"   Test  : {counts['test']} images")
    print(f"   Skipped (missing files): {skipped}")
    print(f"\n   YAML written → {OUTPUT_DIR}/dataset.yaml")
    print(f"   Class mapping: {dict(enumerate([categories[k] for k in sorted(categories.keys())]))}")

if __name__ == "__main__":
    convert_and_split()