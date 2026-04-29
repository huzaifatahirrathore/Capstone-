

"""
compare.py — Vegetation change analysis between two images.

Runs the trained YOLO tree detector on both images, then divides each image
into a configurable grid and computes per-cell tree-canopy coverage.
The delta between the two is used to classify each zone as:
  - GAINED     (green)   : coverage increased significantly
  - DECLINING  (orange)  : coverage dropped moderately
  - ENDANGERED (red)     : coverage dropped severely
  - STABLE     (gray)    : little or no change

Usage:
    python compare.py before.jpg after.jpg
    python compare.py before.jpg after.jpg --conf 0.3 --grid-rows 6 --grid-cols 6
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MODEL_PATH = "best.pt"

GRID_ROWS = 4
GRID_COLS = 4

# Coverage delta thresholds (fraction, not percent)
GAIN_THRESHOLD       =  0.05   # +5 pp → gained
LOSS_THRESHOLD       = -0.05   # −5 pp → declining
ENDANGERED_THRESHOLD = -0.20   # −20 pp → potentially endangered
# ──────────────────────────────────────────────────────────────────────────────


# ── Detection helpers ─────────────────────────────────────────────────────────

def get_detections(model: YOLO, image_path: str, conf: float):
    """Run the model on *image_path* and return (boxes, annotated_bgr)."""
    results = model(image_path, conf=conf, iou=0.7)[0]
    return results.boxes, results.plot()


# ── Coverage computation ──────────────────────────────────────────────────────

def compute_grid_coverage(boxes, img_w: int, img_h: int,
                          rows: int, cols: int) -> np.ndarray:
    """
    For every grid cell compute the fraction of its area covered by bounding
    boxes (capped at 1.0 — multiple overlapping boxes are additive up to full).

    Returns a (rows × cols) float32 array in [0, 1].
    """
    cell_w = img_w / cols
    cell_h = img_h / rows
    coverage = np.zeros((rows, cols), dtype=np.float32)

    if boxes is None or len(boxes) == 0:
        return coverage

    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        if (x2 - x1) <= 0 or (y2 - y1) <= 0:
            continue

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


# ── Visualisation helpers ─────────────────────────────────────────────────────

def _cell_color(delta_val: float):
    """Return (BGR_color, label_str, text_BGR) for a given delta value."""
    if delta_val <= ENDANGERED_THRESHOLD:
        return (0, 0, 200), f"DANGER\n{delta_val*100:+.0f}%", (0, 0, 255)
    if delta_val <= LOSS_THRESHOLD:
        return (0, 100, 255), f"{delta_val*100:+.0f}%", (0, 100, 255)
    if delta_val >= GAIN_THRESHOLD:
        return (0, 180, 0),   f"{delta_val*100:+.0f}%", (0, 200, 0)
    return (150, 150, 150),   f"{delta_val*100:+.0f}%", (200, 200, 200)


def build_change_overlay(img_w: int, img_h: int, delta: np.ndarray,
                         rows: int, cols: int, alpha: int = 90) -> np.ndarray:
    """Return an BGRA overlay image with colour-coded grid cells."""
    overlay = np.zeros((img_h, img_w, 4), dtype=np.uint8)
    cell_w = img_w // cols
    cell_h = img_h // rows

    for r in range(rows):
        for c in range(cols):
            bgr, _, _ = _cell_color(delta[r, c])
            # Endangered gets higher opacity so it stands out
            cell_alpha = 140 if delta[r, c] <= ENDANGERED_THRESHOLD else alpha
            x1, y1 = c * cell_w, r * cell_h
            x2, y2 = x1 + cell_w, y1 + cell_h
            overlay[y1:y2, x1:x2] = (*bgr, cell_alpha)

    return overlay


def blend_overlay(base: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
    """Alpha-blend a BGRA overlay onto a BGR base image."""
    alpha  = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
    color  = overlay_rgba[:, :, :3].astype(np.float32)
    result = base.astype(np.float32) * (1 - alpha) + color * alpha
    return result.astype(np.uint8)


def draw_grid_labels(img: np.ndarray, delta: np.ndarray,
                     rows: int, cols: int) -> np.ndarray:
    """Draw delta labels and grid lines onto *img* (in-place copy)."""
    result = img.copy()
    img_h, img_w = result.shape[:2]
    cell_w = img_w // cols
    cell_h = img_h // rows

    for r in range(rows):
        for c in range(cols):
            _, label, txt_color = _cell_color(delta[r, c])
            cx = c * cell_w + cell_w // 2
            cy = r * cell_h + cell_h // 2
            lines = label.split("\n")
            for i, line in enumerate(lines):
                y = cy - (len(lines) - 1) * 10 + i * 20
                # Black outline for readability
                cv2.putText(result, line, (cx - 35, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(result, line, (cx - 35, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, txt_color, 1, cv2.LINE_AA)

    # Grid lines
    for r in range(1, rows):
        y = r * cell_h
        cv2.line(result, (0, y), (img_w, y), (255, 255, 255), 1)
    for c in range(1, cols):
        x = c * cell_w
        cv2.line(result, (x, 0), (x, img_h), (255, 255, 255), 1)

    return result


def add_legend(img: np.ndarray) -> np.ndarray:
    """Append a legend bar at the bottom of the composite image."""
    h, w = img.shape[:2]
    bar = np.full((40, w, 3), 30, dtype=np.uint8)
    items = [
        ((0, 200, 0),   "Gained"),
        ((0, 100, 255), "Declining"),
        ((0, 0, 255),   "Endangered"),
        ((200, 200, 200), "Stable"),
    ]
    x = 10
    for bgr, label in items:
        cv2.rectangle(bar, (x, 10), (x + 20, 30), bgr, -1)
        cv2.putText(bar, label, (x + 25, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)
        x += 130
    return np.vstack([img, bar])


def make_header(text: str, width: int) -> np.ndarray:
    bar = np.zeros((30, width, 3), dtype=np.uint8)
    cv2.putText(bar, text, (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return bar


# ── Main comparison logic ─────────────────────────────────────────────────────

def compare(before_path: str, after_path: str,
            conf: float = 0.25,
            grid_rows: int = GRID_ROWS,
            grid_cols: int = GRID_COLS,
            save: bool = True):
    """
    Full vegetation comparison pipeline.

    Parameters
    ----------
    before_path : path to the earlier / baseline image
    after_path  : path to the later / comparison image
    conf        : YOLO confidence threshold
    grid_rows   : number of horizontal grid bands
    grid_cols   : number of vertical grid bands
    save        : whether to write the composite image to disk

    Returns
    -------
    (delta, cov_before, cov_after) — all (grid_rows × grid_cols) numpy arrays
    """
    for p in (before_path, after_path):
        if not Path(p).exists():
            print(f"Error: image not found — {p}")
            sys.exit(1)

    model = YOLO(MODEL_PATH)

    # ── Detect ────────────────────────────────────────────────────────────────
    boxes_before, ann_before = get_detections(model, before_path, conf)
    boxes_after,  ann_after  = get_detections(model, after_path,  conf)

    h_b, w_b = ann_before.shape[:2]
    h_a, w_a = ann_after.shape[:2]

    # If sizes differ, resize 'after' to match 'before' so the grid lines up
    if (h_b, w_b) != (h_a, w_a):
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = str(tmp_dir / "resized_after_compare.jpg")
        cv2.imwrite(tmp_path, cv2.resize(cv2.imread(after_path), (w_b, h_b)))
        boxes_after, ann_after = get_detections(model, tmp_path, conf)
        h_a, w_a = h_b, w_b

    img_w, img_h = w_b, h_b

    # ── Coverage grids ────────────────────────────────────────────────────────
    cov_before = compute_grid_coverage(boxes_before, img_w, img_h, grid_rows, grid_cols)
    cov_after  = compute_grid_coverage(boxes_after,  img_w, img_h, grid_rows, grid_cols)
    delta      = cov_after - cov_before

    # ── Console report ────────────────────────────────────────────────────────
    n_before = len(boxes_before)
    n_after  = len(boxes_after)
    avg_cov_before = float(cov_before.mean()) * 100
    avg_cov_after  = float(cov_after.mean())  * 100

    gained     = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
                  if delta[r, c] >= GAIN_THRESHOLD]
    declining  = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
                  if ENDANGERED_THRESHOLD < delta[r, c] <= LOSS_THRESHOLD]
    endangered = [(r, c) for r in range(grid_rows) for c in range(grid_cols)
                  if delta[r, c] <= ENDANGERED_THRESHOLD]

    print("\n" + "=" * 62)
    print("  VEGETATION COMPARISON REPORT")
    print("=" * 62)
    print(f"  Before : {Path(before_path).name:<40}  {n_before:>3} tree(s)")
    print(f"  After  : {Path(after_path).name:<40}  {n_after:>3} tree(s)")
    print(f"  Tree count change     : {n_after - n_before:+d}")
    print(f"  Avg grid coverage     : {avg_cov_before:.1f}%  →  {avg_cov_after:.1f}%"
          f"  ({avg_cov_after - avg_cov_before:+.1f} pp)")
    print()

    if gained:
        print(f"  GAINED vegetation  — {len(gained)} zone(s):")
        for r, c in gained:
            print(f"    Grid row {r+1}/{grid_rows}, col {c+1}/{grid_cols}"
                  f"  coverage {cov_before[r,c]*100:.1f}% → {cov_after[r,c]*100:.1f}%"
                  f"  ({delta[r,c]*100:+.1f} pp)")

    if declining:
        print(f"  DECLINING vegetation — {len(declining)} zone(s):")
        for r, c in declining:
            print(f"    Grid row {r+1}/{grid_rows}, col {c+1}/{grid_cols}"
                  f"  coverage {cov_before[r,c]*100:.1f}% → {cov_after[r,c]*100:.1f}%"
                  f"  ({delta[r,c]*100:+.1f} pp)")

    if endangered:
        print(f"  *** POTENTIALLY ENDANGERED — {len(endangered)} zone(s) ***")
        for r, c in endangered:
            print(f"    Grid row {r+1}/{grid_rows}, col {c+1}/{grid_cols}"
                  f"  coverage {cov_before[r,c]*100:.1f}% → {cov_after[r,c]*100:.1f}%"
                  f"  ({delta[r,c]*100:+.1f} pp)  ← significant loss")

    if not gained and not declining and not endangered:
        print("  No significant vegetation change detected across any zone.")

    print("=" * 62 + "\n")

    # ── Composite image ───────────────────────────────────────────────────────
    if save:
        overlay    = build_change_overlay(img_w, img_h, delta, grid_rows, grid_cols)
        change_map = blend_overlay(ann_after, overlay)
        change_map = draw_grid_labels(change_map, delta, grid_rows, grid_cols)

        # Pad both panels to equal height
        target_h = max(h_b, change_map.shape[0])
        pad_b = cv2.copyMakeBorder(ann_before,   0, target_h - h_b,
                                   0, 0, cv2.BORDER_CONSTANT)
        pad_a = cv2.copyMakeBorder(change_map,   0, target_h - change_map.shape[0],
                                   0, 0, cv2.BORDER_CONSTANT)

        col_b = np.vstack([make_header(f"BEFORE  ({n_before} trees)", w_b), pad_b])
        col_a = np.vstack([make_header(f"AFTER   ({n_after} trees)",  img_w), pad_a])

        # Final height alignment before hstack
        h1, h2 = col_b.shape[0], col_a.shape[0]
        if h1 < h2:
            col_b = cv2.copyMakeBorder(col_b, 0, h2 - h1, 0, 0, cv2.BORDER_CONSTANT)
        elif h2 < h1:
            col_a = cv2.copyMakeBorder(col_a, 0, h1 - h2, 0, 0, cv2.BORDER_CONSTANT)

        composite = add_legend(np.hstack([col_b, col_a]))

        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        stem_b   = Path(before_path).stem
        stem_a   = Path(after_path).stem
        out_path = out_dir / f"compare_{stem_b}_vs_{stem_a}.jpg"
        cv2.imwrite(str(out_path), composite)
        print(f"Comparison image saved to: {out_path}")

    return delta, cov_before, cov_after


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare vegetation coverage between two images using the trained YOLO tree detector."
    )
    parser.add_argument("before",        help="Path to the BEFORE (baseline) image")
    parser.add_argument("after",         help="Path to the AFTER image")
    parser.add_argument("--conf",        type=float, default=0.25,
                        help="Confidence threshold (default: 0.25)")
    parser.add_argument("--grid-rows",   type=int,   default=GRID_ROWS,
                        help=f"Number of grid rows (default: {GRID_ROWS})")
    parser.add_argument("--grid-cols",   type=int,   default=GRID_COLS,
                        help=f"Number of grid columns (default: {GRID_COLS})")
    parser.add_argument("--no-save",     action="store_true",
                        help="Don't save the comparison image")
    args = parser.parse_args()

    compare(
        args.before,
        args.after,
        conf=args.conf,
        grid_rows=args.grid_rows,
        grid_cols=args.grid_cols,
        save=not args.no_save,
    )