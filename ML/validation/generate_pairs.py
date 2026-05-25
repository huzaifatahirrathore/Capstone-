"""
generate_pairs.py — Automated synthetic before/after pair generation for
                    forest vegetation-change validation.

For each source drone image we produce a triple:
    before.jpg       : the original image
    after.jpg        : a deliberately modified copy
    loss_truth.png   : binary mask of vegetation we removed (in BEFORE frame)
    growth_truth.png : binary mask of vegetation we added   (in BEFORE frame)

Because we authored every pixel-level change ourselves, the ground truth
is perfect — no manual annotation required.

Categories
----------
  identity         before == after (sanity / false-positive baseline)
  lighting         same scene, different lighting only
  homography       same scene, slight camera-angle change only
  loss_clean       N trees inpainted away, nothing else changed
  loss_realistic   N trees inpainted + lighting + homography + JPEG
  loss_small       only 1–2 small trees removed (sensitivity floor)
  growth           trees pasted onto sparse regions
  mixed            loss + growth + realistic perturbations in one pair

Usage
-----
    python generate_pairs.py --num 50
    python generate_pairs.py --num 200 --seed 1 --out pairs_v2
    python generate_pairs.py --num 50 --categories loss_realistic mixed

Source images default to ../train/dataset/images/val/.
YOLO model defaults to the trained checkpoint in ../train/runs/.
Runs on CPU by default so it doesn't fight a concurrent SAM/training job.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Lazy import — only loaded if we need to detect masks from scratch
YOLO = None


# ─── DEFAULTS ─────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).resolve().parent
PROJECT_ROOT   = SCRIPT_DIR.parent
SOURCE_DEFAULT = PROJECT_ROOT / "train" / "dataset" / "images" / "val"
MODEL_DEFAULT  = (PROJECT_ROOT / "train" / "runs" / "detect" / "runs" /
                  "tree_detect" / "yolo26m_trees-8" / "weights" / "best.pt")
OUT_DEFAULT    = SCRIPT_DIR / "pairs"

ALL_CATEGORIES = [
    "identity", "lighting", "homography",
    "loss_clean", "loss_realistic", "loss_small",
    "growth", "mixed",
]

# YOLO inference settings (CPU-friendly defaults)
YOLO_CONF  = 0.25
YOLO_IOU   = 0.6
YOLO_IMGSZ = 1280

# HSV vegetation band used to refine bbox → polygon mask
HSV_GREEN_LOW  = (25,  30,  30)
HSV_GREEN_HIGH = (95, 255, 255)


# ─── MASK EXTRACTION ──────────────────────────────────────────────────────────

def _green_mask(img_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, np.array(HSV_GREEN_LOW), np.array(HSV_GREEN_HIGH))


def extract_tree_masks(image_path: Path, model, device: str) -> list[np.ndarray]:
    """
    Return one binary mask per detected tree.

    Strategy: run YOLO to get bboxes, then keep only green pixels within
    each bbox. This is a faster, GPU-light proxy for SAM-refined masks
    and avoids any conflict with a running SAM job.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return []

    res = model(str(image_path), conf=YOLO_CONF, iou=YOLO_IOU,
                imgsz=YOLO_IMGSZ, device=device, verbose=False)[0]
    if len(res.boxes) == 0:
        return []

    H, W = img.shape[:2]
    green = _green_mask(img)

    masks: list[np.ndarray] = []
    for box in res.boxes:
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        m = np.zeros((H, W), dtype=np.uint8)
        m[y1:y2, x1:x2] = green[y1:y2, x1:x2]
        if int(m.sum()) > 0:
            masks.append(m)
    return masks


def load_seg_masks(label_path: Path, img_shape: tuple[int, int]) -> list[np.ndarray]:
    """
    Load SAM-refined polygon masks from a YOLO-seg label file.

    Each line in the .txt is: `cls_id x1 y1 x2 y2 ... xn yn`
    where coords are normalized to [0, 1].
    """
    H, W = img_shape
    masks: list[np.ndarray] = []
    if not label_path.exists():
        return masks

    for line in label_path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 7:                    # need at least 3 points
            continue
        coords = list(map(float, parts[1:]))
        pts = np.array([(coords[i] * W, coords[i + 1] * H)
                        for i in range(0, len(coords) - 1, 2)],
                       dtype=np.int32)
        m = np.zeros((H, W), dtype=np.uint8)
        cv2.fillPoly(m, [pts], 255)
        if int(m.sum()) > 0:
            masks.append(m)
    return masks


# ─── INPAINTING (vegetation loss) ─────────────────────────────────────────────

def inpaint_trees(img: np.ndarray, masks: list[np.ndarray],
                  dilate_px: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """
    Paint over the given tree masks using cv2.inpaint, blending each
    tree with its surrounding ground texture. Returns:
        (modified_image, combined_loss_mask)
    """
    if not masks:
        return img.copy(), np.zeros(img.shape[:2], dtype=np.uint8)

    combined = np.zeros(img.shape[:2], dtype=np.uint8)
    for m in masks:
        combined = cv2.bitwise_or(combined, m)

    # Dilate slightly so we cover the soft tree-edge halo that HSV missed
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (dilate_px * 2 + 1, dilate_px * 2 + 1))
    dilated = cv2.dilate(combined, kernel)

    inpainted = cv2.inpaint(img, dilated, inpaintRadius=5,
                            flags=cv2.INPAINT_TELEA)

    # Feather the result back into the original so the boundary isn't sharp
    soft = cv2.GaussianBlur(dilated.astype(np.float32) / 255.0,
                            (15, 15), 0)[..., None]
    blended = (img * (1 - soft) + inpainted * soft).astype(np.uint8)

    return blended, combined        # report truth at the original mask edges


# ─── TREE PASTING (vegetation growth) ─────────────────────────────────────────

def paste_trees(target: np.ndarray, source: np.ndarray,
                source_masks: list[np.ndarray],
                num: int, rng: random.Random
                ) -> tuple[np.ndarray, np.ndarray]:
    """
    Copy `num` tree instances from `source` onto `target`, placing each
    one over a relatively-bare patch of the target image.
    """
    if num <= 0 or not source_masks:
        return target.copy(), np.zeros(target.shape[:2], dtype=np.uint8)

    H, W = target.shape[:2]
    target_green = _green_mask(target)
    out = target.copy()
    truth = np.zeros((H, W), dtype=np.uint8)

    picked = rng.sample(source_masks, k=min(num, len(source_masks)))

    for m in picked:
        ys, xs = np.where(m > 0)
        if ys.size == 0:
            continue
        y_min, y_max = int(ys.min()), int(ys.max())
        x_min, x_max = int(xs.min()), int(xs.max())
        tile_h = y_max - y_min + 1
        tile_w = x_max - x_min + 1
        if tile_h >= H or tile_w >= W:
            continue

        # Find a sparse target location (try 12 candidates, pick the one
        # with the least green overlap)
        best_xy, best_score = None, float("inf")
        for _ in range(12):
            tx = rng.randint(0, W - tile_w - 1)
            ty = rng.randint(0, H - tile_h - 1)
            score = int(target_green[ty:ty + tile_h, tx:tx + tile_w].sum())
            if score < best_score:
                best_score, best_xy = score, (tx, ty)
        if best_xy is None:
            continue
        tx, ty = best_xy

        # Extract the tree tile and its mask
        tile = source[y_min:y_max + 1, x_min:x_max + 1]
        tile_mask = m[y_min:y_max + 1, x_min:x_max + 1]

        # Seamless paste with soft alpha (Gaussian-feathered mask)
        alpha = cv2.GaussianBlur(tile_mask.astype(np.float32) / 255.0,
                                 (9, 9), 0)[..., None]
        roi = out[ty:ty + tile_h, tx:tx + tile_w].astype(np.float32)
        blended = roi * (1 - alpha) + tile.astype(np.float32) * alpha
        out[ty:ty + tile_h, tx:tx + tile_w] = blended.astype(np.uint8)

        # Update ground-truth growth mask
        truth[ty:ty + tile_h, tx:tx + tile_w] = np.maximum(
            truth[ty:ty + tile_h, tx:tx + tile_w], tile_mask)

    return out, truth


# ─── PERTURBATIONS ────────────────────────────────────────────────────────────

@dataclass
class LightingParams:
    brightness: float = 1.0     # multiplicative on V
    contrast:   float = 1.0     # alpha on BGR
    hue_shift:  int   = 0       # degrees on H
    saturation: float = 1.0     # multiplicative on S


def perturb_lighting(img: np.ndarray, rng: random.Random
                     ) -> tuple[np.ndarray, LightingParams]:
    p = LightingParams(
        brightness=rng.uniform(0.75, 1.25),
        contrast=  rng.uniform(0.85, 1.15),
        hue_shift= rng.randint(-10, 10),
        saturation=rng.uniform(0.80, 1.20),
    )
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + p.hue_shift) % 180
    hsv[..., 1] = np.clip(hsv[..., 1] * p.saturation, 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] * p.brightness, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    out = cv2.convertScaleAbs(out, alpha=p.contrast, beta=0)
    return out, p


@dataclass
class HomographyParams:
    max_corner_shift_px: int = 12
    matrix: list[list[float]] = field(default_factory=list)


def perturb_homography(img: np.ndarray, rng: random.Random,
                       max_shift: int = 12
                       ) -> tuple[np.ndarray, HomographyParams]:
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    jitter = np.array([[rng.uniform(-max_shift, max_shift),
                        rng.uniform(-max_shift, max_shift)] for _ in range(4)],
                      dtype=np.float32)
    dst = src + jitter
    H = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, H, (w, h), borderMode=cv2.BORDER_REFLECT)
    return warped, HomographyParams(max_corner_shift_px=max_shift,
                                    matrix=H.tolist())


def perturb_jpeg(img: np.ndarray, rng: random.Random
                 ) -> tuple[np.ndarray, int]:
    quality = rng.randint(72, 92)
    ok, enc = cv2.imencode(".jpg", img,
                           [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return img, 100
    return cv2.imdecode(enc, cv2.IMREAD_COLOR), quality


def perturb_noise(img: np.ndarray, rng: random.Random,
                  sigma_max: float = 4.0) -> tuple[np.ndarray, float]:
    sigma = rng.uniform(0.5, sigma_max)
    noise = np.random.RandomState(rng.randint(0, 1_000_000)).normal(
        0, sigma, img.shape).astype(np.float32)
    out = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return out, sigma


# ─── PAIR ASSEMBLY ────────────────────────────────────────────────────────────

@dataclass
class PairMeta:
    pair_id:        str
    category:       str
    source_image:   str
    source_h:       int
    source_w:       int
    n_trees_total:  int
    n_trees_lost:   int   = 0
    n_trees_added:  int   = 0
    seed:           int   = 0
    perturbations:  dict  = field(default_factory=dict)
    mask_source:    str   = "yolo+hsv"


def _zero_mask(img: np.ndarray) -> np.ndarray:
    return np.zeros(img.shape[:2], dtype=np.uint8)


def _select_masks(masks: list[np.ndarray], frac: float,
                  rng: random.Random) -> list[np.ndarray]:
    if not masks:
        return []
    n = max(1, int(round(len(masks) * frac)))
    n = min(n, len(masks))
    return rng.sample(masks, k=n)


def _select_small_masks(masks: list[np.ndarray], n: int,
                        rng: random.Random) -> list[np.ndarray]:
    """Prefer smaller-area masks (tests sensitivity to subtle change)."""
    if not masks:
        return []
    by_size = sorted(masks, key=lambda m: int(m.sum()))
    candidates = by_size[:max(n * 3, 4)]
    return rng.sample(candidates, k=min(n, len(candidates)))


def build_pair(category: str,
               before: np.ndarray,
               masks: list[np.ndarray],
               donor_img: Optional[np.ndarray],
               donor_masks: Optional[list[np.ndarray]],
               rng: random.Random
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                          int, int, dict]:
    """
    Returns (after_img, loss_truth, growth_truth,
             n_trees_lost, n_trees_added, perturbation_meta).
    Truth masks are in BEFORE coordinate frame.
    Caller guarantees a valid donor when category needs one.
    """
    meta_perturb: dict = {}
    n_lost = 0
    n_added = 0
    after = before.copy()
    loss_truth = _zero_mask(before)
    growth_truth = _zero_mask(before)

    if category == "identity":
        pass

    elif category == "lighting":
        after, p = perturb_lighting(after, rng)
        meta_perturb["lighting"] = asdict(p)

    elif category == "homography":
        after, h = perturb_homography(after, rng)
        meta_perturb["homography"] = asdict(h)

    elif category == "loss_clean":
        chosen = _select_masks(masks, frac=rng.uniform(0.15, 0.30), rng=rng)
        after, loss_truth = inpaint_trees(after, chosen)
        n_lost = len(chosen)

    elif category == "loss_small":
        chosen = _select_small_masks(masks, n=rng.randint(1, 2), rng=rng)
        after, loss_truth = inpaint_trees(after, chosen)
        n_lost = len(chosen)

    elif category == "loss_realistic":
        chosen = _select_masks(masks, frac=rng.uniform(0.10, 0.25), rng=rng)
        after, loss_truth = inpaint_trees(after, chosen)
        n_lost = len(chosen)
        after, p_l = perturb_lighting(after, rng); meta_perturb["lighting"] = asdict(p_l)
        after, p_h = perturb_homography(after, rng); meta_perturb["homography"] = asdict(p_h)
        after, q    = perturb_jpeg(after, rng);     meta_perturb["jpeg_quality"] = q
        after, s    = perturb_noise(after, rng);    meta_perturb["noise_sigma"] = s

    elif category == "growth":
        # Driver guarantees donor is non-empty for this category
        assert donor_img is not None and donor_masks, \
            "growth category requires a donor — driver should have skipped"
        n_to_add = rng.randint(2, 5)
        after, growth_truth = paste_trees(after, donor_img, donor_masks,
                                          num=n_to_add, rng=rng)
        n_added = n_to_add if int(growth_truth.sum()) > 0 else 0

    elif category == "mixed":
        # Loss + growth + realistic perturbations
        chosen = _select_masks(masks, frac=rng.uniform(0.10, 0.20), rng=rng)
        after, loss_truth = inpaint_trees(after, chosen)
        n_lost = len(chosen)
        if donor_img is not None and donor_masks:
            n_to_add = rng.randint(1, 3)
            after, growth_truth = paste_trees(after, donor_img, donor_masks,
                                              num=n_to_add, rng=rng)
            n_added = n_to_add
        after, p_l = perturb_lighting(after, rng); meta_perturb["lighting"] = asdict(p_l)
        after, p_h = perturb_homography(after, rng); meta_perturb["homography"] = asdict(p_h)
        after, q    = perturb_jpeg(after, rng);     meta_perturb["jpeg_quality"] = q

    else:
        raise ValueError(f"Unknown category: {category}")

    return after, loss_truth, growth_truth, n_lost, n_added, meta_perturb


# ─── DRIVER ───────────────────────────────────────────────────────────────────

def _load_model(model_path: Path, device: str):
    global YOLO
    if YOLO is None:
        from ultralytics import YOLO as _Y
        YOLO = _Y
    if not model_path.exists():
        sys.exit(f"YOLO model not found: {model_path}")
    print(f"Loading YOLO ({device}): {model_path.name}")
    return YOLO(str(model_path))


def _find_seg_label(image_path: Path, seg_root: Path) -> Optional[Path]:
    """Locate the matching .txt under seg_root, regardless of which split."""
    stem = image_path.stem
    for split in ("train", "val", "test"):
        candidate = seg_root / split / f"{stem}.txt"
        if candidate.exists():
            return candidate
    direct = seg_root / f"{stem}.txt"
    return direct if direct.exists() else None


def generate(source_dir: Path, out_dir: Path, num: int,
             categories: list[str], seed: int, device: str,
             model_path: Path, seg_root: Optional[Path],
             min_trees: int = 4) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    images = sorted([p for p in source_dir.iterdir()
                     if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if not images:
        sys.exit(f"No images found under: {source_dir}")
    print(f"Found {len(images)} source images under {source_dir}")

    mask_source = "sam_polygons" if seg_root else "yolo+hsv"
    model = None if seg_root else _load_model(model_path, device)
    print(f"Mask source: {mask_source}")
    print(f"Categories : {categories}")
    print(f"Generating : {num} pairs → {out_dir}\n")

    # Cache (image, masks) so growth donors don't re-detect
    cache: dict[str, tuple[np.ndarray, list[np.ndarray]]] = {}

    def _get(image_path: Path) -> tuple[np.ndarray, list[np.ndarray]]:
        key = str(image_path)
        if key in cache:
            return cache[key]
        img = cv2.imread(key)
        if img is None:
            cache[key] = (np.zeros((1, 1, 3), dtype=np.uint8), [])
            return cache[key]
        if seg_root:
            label_path = _find_seg_label(image_path, seg_root)
            ms = (load_seg_masks(label_path, img.shape[:2])
                  if label_path else [])
        else:
            ms = extract_tree_masks(image_path, model, device)
        cache[key] = (img, ms)
        return cache[key]

    summary: dict[str, int] = {c: 0 for c in categories}
    written = 0
    attempts = 0
    max_attempts = num * 4

    while written < num and attempts < max_attempts:
        attempts += 1
        category = categories[written % len(categories)]
        src = rng.choice(images)
        before, masks = _get(src)

        # Skip images with too few trees for loss/mixed categories
        needs_trees = category in {"loss_clean", "loss_realistic",
                                   "loss_small", "mixed"}
        if needs_trees and len(masks) < min_trees:
            continue

        donor_img, donor_masks = None, None
        if category in {"growth", "mixed"}:
            for _ in range(8):
                cand = rng.choice(images)
                if cand == src:
                    continue
                d_img, d_ms = _get(cand)
                if len(d_ms) >= 2:
                    donor_img, donor_masks = d_img, d_ms
                    break
            if category == "growth" and donor_masks is None:
                continue

        (after, loss_truth, growth_truth,
         n_lost, n_added, perturb_meta) = build_pair(
            category, before, masks, donor_img, donor_masks, rng)

        pair_id  = f"pair_{written + 1:04d}"
        pair_dir = out_dir / pair_id
        pair_dir.mkdir(exist_ok=True)

        cv2.imwrite(str(pair_dir / "before.jpg"),       before,
                    [cv2.IMWRITE_JPEG_QUALITY, 95])
        cv2.imwrite(str(pair_dir / "after.jpg"),        after,
                    [cv2.IMWRITE_JPEG_QUALITY, 95])
        cv2.imwrite(str(pair_dir / "loss_truth.png"),   loss_truth)
        cv2.imwrite(str(pair_dir / "growth_truth.png"), growth_truth)

        meta = PairMeta(
            pair_id=pair_id, category=category,
            source_image=str(src.relative_to(PROJECT_ROOT)),
            source_h=before.shape[0], source_w=before.shape[1],
            n_trees_total=len(masks),
            n_trees_lost=n_lost, n_trees_added=n_added,
            seed=seed + written, perturbations=perturb_meta,
            mask_source=mask_source,
        )
        (pair_dir / "meta.json").write_text(json.dumps(asdict(meta), indent=2))

        summary[category] = summary.get(category, 0) + 1
        written += 1
        print(f"[{written:4d}/{num}] {category:<15s} {pair_id}  "
              f"src={src.name[:32]:32s}  "
              f"loss={n_lost} growth={n_added}  "
              f"({int(loss_truth.sum() / 255):>7,}px loss, "
              f"{int(growth_truth.sum() / 255):>7,}px growth)")

    print()
    print("=" * 70)
    print(f"Generated {written} pairs ({attempts} attempts) → {out_dir}")
    for cat, count in summary.items():
        print(f"  {cat:<18s} {count:>4d}")
    if written < num:
        print(f"\nWarning: only generated {written}/{num}. Source pool may "
              f"have too few images with ≥{min_trees} detected trees.")
    print("=" * 70)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Generate synthetic before/after pairs with ground truth.")
    p.add_argument("--source", type=Path, default=SOURCE_DEFAULT,
                   help=f"Directory of source drone images "
                        f"(default: {SOURCE_DEFAULT.relative_to(PROJECT_ROOT)})")
    p.add_argument("--out", type=Path, default=OUT_DEFAULT,
                   help=f"Output directory (default: "
                        f"{OUT_DEFAULT.relative_to(PROJECT_ROOT)})")
    p.add_argument("--num", type=int, default=50,
                   help="Number of pairs to generate (default: 50)")
    p.add_argument("--seed", type=int, default=42, help="RNG seed")
    p.add_argument("--categories", nargs="+", default=ALL_CATEGORIES,
                   choices=ALL_CATEGORIES,
                   help="Subset of categories to generate "
                        "(default: all 8)")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda", "0"],
                   help="YOLO device — defaults to cpu so it doesn't fight "
                        "a concurrent SAM/training job")
    p.add_argument("--model", type=Path, default=MODEL_DEFAULT,
                   help="Path to YOLO checkpoint (ignored if --seg-labels set)")
    p.add_argument("--seg-labels", type=Path, default=None,
                   help="Path to dataset/labels_seg directory of SAM-refined "
                        "polygons. If provided, no YOLO inference is done.")
    p.add_argument("--min-trees", type=int, default=4,
                   help="Skip images with fewer detected trees than this "
                        "for loss/mixed categories")
    args = p.parse_args()

    if not args.source.exists():
        sys.exit(f"Source directory does not exist: {args.source}")

    generate(
        source_dir=args.source,
        out_dir=args.out,
        num=args.num,
        categories=args.categories,
        seed=args.seed,
        device=args.device,
        model_path=args.model,
        seg_root=args.seg_labels,
        min_trees=args.min_trees,
    )


if __name__ == "__main__":
    main()
