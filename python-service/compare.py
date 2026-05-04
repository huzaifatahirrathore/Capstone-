"""
compare.py — Vegetation change analysis between two images.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
from db import get_connection
import json

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MODEL_PATH = "best.pt"

GRID_ROWS = 4
GRID_COLS = 4

GAIN_THRESHOLD       =  0.05
LOSS_THRESHOLD       = -0.05
ENDANGERED_THRESHOLD = -0.20


# ──────────────────────────────────────────────────────────────────────────────
# DB SAVE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def save_comparison_to_db(before_path, after_path, tree_change,
                          avg_change, gained, declining,
                          endangered, delta):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO comparisons (
            before_image,
            after_image,
            tree_change,
            avg_coverage_change,
            gained_zones,
            declining_zones,
            endangered_zones,
            delta
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        before_path,
        after_path,
        tree_change,
        avg_change,
        len(gained),
        len(declining),
        len(endangered),
        json.dumps(delta.tolist())
    ))

    conn.commit()
    cur.close()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# MODEL HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def get_detections(model: YOLO, image_path: str, conf: float):
    results = model(image_path, conf=conf, iou=0.7)[0]
    return results.boxes, results.plot()


def compute_grid_coverage(boxes, img_w: int, img_h: int, rows: int, cols: int):
    cell_w = img_w / cols
    cell_h = img_h / rows
    coverage = np.zeros((rows, cols), dtype=np.float32)

    if boxes is None or len(boxes) == 0:
        return coverage

    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        for r in range(rows):
            for c in range(cols):
                cx1 = c * cell_w
                cy1 = r * cell_h
                cx2 = cx1 + cell_w
                cy2 = cy1 + cell_h

                ix1 = max(x1, cx1)
                iy1 = max(y1, cy1)
                ix2 = min(x2, cx2)
                iy2 = min(y2, cy2)

                if ix2 > ix1 and iy2 > iy1:
                    coverage[r, c] += (ix2 - ix1) * (iy2 - iy1) / (cell_w * cell_h)

    return np.clip(coverage, 0.0, 1.0)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def compare(before_path: str, after_path: str,
            conf: float = 0.25,
            grid_rows: int = GRID_ROWS,
            grid_cols: int = GRID_COLS,
            save: bool = True):

    for p in (before_path, after_path):
        if not Path(p).exists():
            print(f"Error: image not found — {p}")
            sys.exit(1)

    model = YOLO(MODEL_PATH)

    boxes_before, ann_before = get_detections(model, before_path, conf)
    boxes_after, ann_after = get_detections(model, after_path, conf)

    h_b, w_b = ann_before.shape[:2]
    h_a, w_a = ann_after.shape[:2]

    if (h_b, w_b) != (h_a, w_a):
        tmp_path = "tmp_resized.jpg"
        cv2.imwrite(tmp_path, cv2.resize(cv2.imread(after_path), (w_b, h_b)))
        boxes_after, ann_after = get_detections(model, tmp_path, conf)

    img_w, img_h = w_b, h_b

    cov_before = compute_grid_coverage(boxes_before, img_w, img_h, grid_rows, grid_cols)
    cov_after  = compute_grid_coverage(boxes_after, img_w, img_h, grid_rows, grid_cols)

    delta = cov_after - cov_before

    n_before = len(boxes_before)
    n_after = len(boxes_after)

    avg_before = float(cov_before.mean()) * 100
    avg_after = float(cov_after.mean()) * 100

    gained = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
              if delta[r, c] >= GAIN_THRESHOLD]

    declining = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
                if ENDANGERED_THRESHOLD < delta[r, c] <= LOSS_THRESHOLD]

    endangered = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
                 if delta[r, c] <= ENDANGERED_THRESHOLD]

    # ─────────────────────────────────────────────────────────────
    # PRINT REPORT
    # ─────────────────────────────────────────────────────────────

    print("\n=== VEGETATION REPORT ===")
    print("Before:", before_path, n_before)
    print("After :", after_path, n_after)
    print("Tree change:", n_after - n_before)
    print("Coverage change:", avg_before, "→", avg_after)

    # ─────────────────────────────────────────────────────────────
    # SAVE TO DATABASE ⭐ (THIS IS THE IMPORTANT ADDITION)
    # ─────────────────────────────────────────────────────────────

    tree_change = n_after - n_before
    avg_change = avg_after - avg_before

    save_comparison_to_db(
        before_path,
        after_path,
        tree_change,
        avg_change,
        gained,
        declining,
        endangered,
        delta
    )

    print("Saved comparison to database ✔")

    return delta, cov_before, cov_after


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--no-save", action="store_true")

    args = parser.parse_args()

    compare(args.before, args.after, conf=args.conf, save=not args.no_save)