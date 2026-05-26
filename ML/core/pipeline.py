"""
pipeline.py — Canonical vegetation-change comparison pipeline.

Single entry point that both validation/metrics.py and train/compare.py
should call. Consolidates Phase 1 (registration → preprocessing → ExG +
joint Otsu → optional YOLO → change-zone diff) into one place so the
grading harness and the production CLI run identical code.

Pipeline stages (each toggleable)
---------------------------------
    1. Registration         — AKAZE features + RANSAC homography
                              (core/registration.py)
    2. Preprocessing        — CLAHE + global histogram matching
                              (core/preprocessing.py)
    3. Vegetation mask      — ExG / ExGR / CIVE / VARI + JOINT Otsu
                              (core/vegetation.py)
                            — or HSV legacy threshold as a fallback
                              (train/canopy.py)
    4. YOLO cross-validation (optional, slow) — drops vegetation regions
                              YOLO confidently disagrees with
    5. Change-zone diff with min_zone_px filter applied to BOTH the raw
       masks and the reported zone list (so the threshold actually
       affects the returned prediction)

Usage
-----
    from core.pipeline import compare_pipeline, load_yolo

    # Simple — defaults are the Phase-1 tuned settings
    result = compare_pipeline("before.jpg", "after.jpg")
    print(f"Loss zones detected: {len(result.loss_zones)}")
    cv2.imwrite("loss.png", result.loss_mask)

    # With YOLO cross-validation
    model = load_yolo("path/to/best.pt", device=0)
    result = compare_pipeline("before.jpg", "after.jpg",
                              use_yolo=True, yolo_model=model, device="0")

    # Disable individual stages to ablate
    result = compare_pipeline("before.jpg", "after.jpg",
                              use_registration=False, use_exg=False)
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

# ─── Make sibling modules importable ──────────────────────────────────────────
_THIS_DIR     = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
_TRAIN_DIR    = _PROJECT_ROOT / "train"
sys.path.insert(0, str(_THIS_DIR))    # core/
sys.path.insert(0, str(_TRAIN_DIR))   # train/canopy.py

from registration  import register                                # noqa: E402
from preprocessing import normalize_pair                          # noqa: E402
from vegetation    import (extract_vegetation_masks_paired,       # noqa: E402
                            continuous_change_masks)
from canopy        import (extract_canopy_mask, cross_validate,   # noqa: E402
                            compute_change_zones)


# ─── DEFAULTS (Phase-1-tuned values) ──────────────────────────────────────────
DEFAULT_MIN_ZONE_PX = 500          # change-zone filter (validated as best balance)
DEFAULT_EXG_METHOD  = "ExG"
DEFAULT_EXG_MIN_DELTA = 20         # continuous-diff: min index drop (0–255) to flag change.
                                   # Swept on synthetic set: 20 ≈ best balance
                                   # (lighting FP 38%→8%, minimal loss-IoU cost).
DEFAULT_CONF        = 0.25
DEFAULT_INFER_IOU   = 0.6
DEFAULT_IMGSZ       = 1280


# ─── RESULT TYPE ──────────────────────────────────────────────────────────────

@dataclass
class ComparisonResult:
    """
    Everything produced by one comparison run. Arrays are returned for
    callers who want to visualize them; dicts are JSON-safe so the
    validation harness can store them.
    """
    # Post-stage images
    before:        np.ndarray   # CLAHE-equalized before (matches mask coordinate frame)
    after:         np.ndarray   # registered + normalized after

    # Vegetation masks (after optional YOLO cross-validation + valid-mask)
    canopy_before: np.ndarray
    canopy_after:  np.ndarray
    valid_mask:    Optional[np.ndarray]   # registration coverage; None if reg disabled

    # Change detection (BOTH masks and zones filtered by min_zone_px)
    loss_mask:     np.ndarray
    growth_mask:   np.ndarray
    loss_zones:    list
    growth_zones:  list

    # Per-stage diagnostics (JSON-safe — no arrays)
    registration:  dict
    preprocessing: dict
    vegetation:    dict
    yolo:          dict

    # Total wall-clock time spent inside compare_pipeline()
    elapsed_s:     float


# ─── INTERNAL HELPERS ─────────────────────────────────────────────────────────

def _load_image(x: Union[str, Path, np.ndarray]) -> np.ndarray:
    """Accept either a path-like or an in-memory BGR array."""
    if isinstance(x, np.ndarray):
        return x
    img = cv2.imread(str(x))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {x}")
    return img


def _filter_by_size(mask: np.ndarray, min_size_px: int) -> np.ndarray:
    """Drop connected components smaller than `min_size_px`."""
    if min_size_px <= 0:
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = np.zeros_like(mask)
    for i in range(1, n):
        if int(stats[i, cv2.CC_STAT_AREA]) >= min_size_px:
            out[labels == i] = 255
    return out


def _zones_from_mask(mask: np.ndarray, min_zone_px: int) -> list:
    """
    Connected-component zones from a binary mask, mirroring the zone dicts
    canopy.compute_change_zones produces (cx, cy, area_px, bbox). Used for the
    continuous-diff path where loss/growth masks are computed directly.
    """
    n, _, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_zone_px:
            continue
        x, y, w, h = (int(stats[i, 0]), int(stats[i, 1]),
                      int(stats[i, 2]), int(stats[i, 3]))
        out.append({"cx": float(cents[i, 0]), "cy": float(cents[i, 1]),
                    "area_px": area, "bbox": (x, y, x + w, y + h)})
    out.sort(key=lambda z: z["area_px"], reverse=True)
    return out


def _yolo_predict(image, model, device: str, conf: float) -> list:
    """Run YOLO. `image` may be a path or a BGR numpy array."""
    source = str(image) if isinstance(image, (str, Path)) else image
    res = model(source, conf=conf, iou=DEFAULT_INFER_IOU,
                imgsz=DEFAULT_IMGSZ, device=device, verbose=False)[0]
    return [[*box.xyxy[0].tolist(), box.conf[0].item(), int(box.cls[0].item())]
            for box in res.boxes]


def _seg_canopy_mask(image, seg_model, device: str, conf: float) -> np.ndarray:
    """
    Run the YOLO-seg model and UNION all per-tree instance masks into a
    single binary canopy-coverage mask (uint8 0/255). This is the learned
    alternative to the ExG/HSV color thresholds — it recognizes tree
    appearance rather than greenness, so it doesn't flicker at canopy edges
    when lighting changes.
    """
    img = image if isinstance(image, np.ndarray) else cv2.imread(str(image))
    H, W = img.shape[:2]
    res = seg_model(img, conf=conf, imgsz=DEFAULT_IMGSZ,
                    device=device, verbose=False)[0]
    canopy = np.zeros((H, W), dtype=np.uint8)
    if res.masks is not None:
        for poly in res.masks.xy:           # polygons in original-image coords
            if poly is not None and len(poly) >= 3:
                cv2.fillPoly(canopy, [poly.astype(np.int32)], 255)
    return canopy


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def compare_pipeline(
    before:            Union[str, Path, np.ndarray],
    after:             Union[str, Path, np.ndarray],
    *,
    use_registration:  bool   = True,
    use_preprocessing: bool   = True,
    vegetation_source: Optional[str] = None,   # "exg" | "hsv" | "seg"
    use_exg:           bool   = True,          # legacy flag (used if vegetation_source is None)
    exg_method:        str    = DEFAULT_EXG_METHOD,
    exg_min_delta:     int    = DEFAULT_EXG_MIN_DELTA,  # continuous-diff magnitude gate
    seg_model:         object = None,          # required when vegetation_source="seg"
    use_yolo:          bool   = False,
    yolo_model:        object = None,
    device:            str    = "cpu",
    conf:              float  = DEFAULT_CONF,
    min_zone_px:       int    = DEFAULT_MIN_ZONE_PX,
) -> ComparisonResult:
    """
    Run the full vegetation-change pipeline on a pair of images.

    Default settings are the Phase-1-tuned values that produced the best
    F1 scores on the synthetic validation set. Each stage can be disabled
    via a `use_*=False` flag for ablation studies or speed.

    The pipeline always returns a result; if registration or vegetation
    extraction fails, the stage's diagnostics dict records `success=False`
    or similar and the pipeline degrades gracefully (uses identity
    alignment / falls back to HSV).
    """
    t0 = time.time()

    before_img = _load_image(before)
    after_img  = _load_image(after)

    # Match shapes (without aligning content — that's registration's job)
    if after_img.shape != before_img.shape:
        after_img = cv2.resize(
            after_img, (before_img.shape[1], before_img.shape[0]),
            interpolation=cv2.INTER_AREA)

    # ── 1) Registration ─────────────────────────────────────────────────────
    if use_registration:
        reg = register(before_img, after_img)
        after_img  = reg.aligned_after
        valid_mask = reg.valid_mask
        reg_info   = reg.diagnostics()
        reg_info.pop("homography", None)   # too bulky for diagnostic output
        reg_info["used"] = True
    else:
        valid_mask = None
        reg_info   = {"used": False}

    # ── 2) Lighting / color normalization ───────────────────────────────────
    if use_preprocessing:
        before_img, after_img, prep = normalize_pair(before_img, after_img)
        prep_info = prep.to_dict()
        prep_info["used"] = True
    else:
        prep_info = {"used": False}

    # ── 3) Vegetation mask extraction ───────────────────────────────────────
    # Resolve the source: explicit vegetation_source wins; otherwise fall
    # back to the legacy use_exg boolean.
    source = vegetation_source or ("exg" if use_exg else "hsv")

    # The ExG path computes loss/growth directly via the continuous-value
    # diff; other sources fall back to a binary mask diff downstream.
    precomputed_loss = precomputed_growth = None

    if source == "seg":
        # EXPERIMENTAL. The seg model does not generalize beyond its training
        # distribution (detected ~0% canopy on real OOD aerial pairs). ExG is
        # the production default. Kept here for experiments only.
        if seg_model is None:
            raise ValueError("vegetation_source='seg' requires seg_model=...")
        canopy_b = _seg_canopy_mask(before_img, seg_model, device, conf)
        canopy_a = _seg_canopy_mask(after_img,  seg_model, device, conf)
        veg_info = {
            "used":            True,
            "method":          "YOLO-seg union",
            "before_fraction": float((canopy_b > 0).sum()) / canopy_b.size,
            "after_fraction":  float((canopy_a > 0).sum()) / canopy_a.size,
        }
    elif source == "exg":
        cc = continuous_change_masks(before_img, after_img,
                                     method=exg_method, min_delta=exg_min_delta)
        canopy_b, canopy_a = cc["canopy_before"], cc["canopy_after"]
        precomputed_loss   = cc["loss_mask"]
        precomputed_growth = cc["growth_mask"]
        veg_info = {
            "used":             True,
            "method":           exg_method,
            "joint_threshold":  True,
            "continuous_diff":  True,
            "min_delta":        cc["min_delta"],
            "otsu_threshold":   cc["otsu_threshold"],
            "before_fraction":  float((canopy_b > 0).sum()) / canopy_b.size,
            "after_fraction":   float((canopy_a > 0).sum()) / canopy_a.size,
        }
    else:  # "hsv"
        canopy_b = extract_canopy_mask(before_img)
        canopy_a = extract_canopy_mask(after_img)
        veg_info = {"used": False, "method": "HSV"}

    # ── 4) YOLO cross-validation (optional) ─────────────────────────────────
    if use_yolo and yolo_model is not None:
        boxes_b = _yolo_predict(before_img, yolo_model, device, conf)
        boxes_a = _yolo_predict(after_img,  yolo_model, device, conf)
        val_b = cross_validate(canopy_b, boxes_b)
        val_a = cross_validate(canopy_a, boxes_a)
        canopy_b = val_b["validated"]
        canopy_a = val_a["validated"]
        yolo_info = {
            "used":               True,
            "n_boxes_before":     len(boxes_b),
            "n_boxes_after":      len(boxes_a),
            "confirmed_before":   len(val_b["confirmed_boxes"]),
            "confirmed_after":    len(val_a["confirmed_boxes"]),
            "false_pos_before":   len(val_b["false_pos_boxes"]),
            "false_pos_after":    len(val_a["false_pos_boxes"]),
        }
    elif use_yolo:
        yolo_info = {"used": True, "error": "yolo_model not provided"}
    else:
        yolo_info = {"used": False}

    # Mask out pixels outside the registration overlap so they don't show as
    # phantom loss/growth on either side.
    if valid_mask is not None:
        canopy_b = cv2.bitwise_and(canopy_b, valid_mask)
        canopy_a = cv2.bitwise_and(canopy_a, valid_mask)
        if precomputed_loss is not None:
            precomputed_loss   = cv2.bitwise_and(precomputed_loss,   valid_mask)
            precomputed_growth = cv2.bitwise_and(precomputed_growth, valid_mask)

    # ── 5) Change-zone diff + size filter ───────────────────────────────────
    # ExG supplies loss/growth directly (continuous diff); other sources diff
    # the binary canopy masks. Either way, filter by min_zone_px so the
    # returned masks match the reported zones.
    if precomputed_loss is not None:
        loss_mask    = _filter_by_size(precomputed_loss,   min_zone_px)
        growth_mask  = _filter_by_size(precomputed_growth, min_zone_px)
        loss_zones   = _zones_from_mask(loss_mask,   min_zone_px)
        growth_zones = _zones_from_mask(growth_mask, min_zone_px)
    else:
        change = compute_change_zones(canopy_b, canopy_a, min_zone_px=min_zone_px)
        loss_mask    = _filter_by_size(change["loss_mask"],   min_zone_px)
        growth_mask  = _filter_by_size(change["growth_mask"], min_zone_px)
        loss_zones   = change["loss_zones"]
        growth_zones = change["growth_zones"]

    return ComparisonResult(
        before=before_img,
        after=after_img,
        canopy_before=canopy_b,
        canopy_after=canopy_a,
        valid_mask=valid_mask,
        loss_mask=loss_mask,
        growth_mask=growth_mask,
        loss_zones=loss_zones,
        growth_zones=growth_zones,
        registration=reg_info,
        preprocessing=prep_info,
        vegetation=veg_info,
        yolo=yolo_info,
        elapsed_s=time.time() - t0,
    )


# ─── YOLO HELPER ──────────────────────────────────────────────────────────────

def load_yolo(model_path: Union[str, Path]):
    """
    Convenience for callers who don't want to import ultralytics themselves.
    Returns a ready-to-use YOLO model object that can be passed to
    `compare_pipeline(..., yolo_model=model)`.
    """
    from ultralytics import YOLO          # noqa: E402  — lazy import
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"YOLO model not found: {path}")
    return YOLO(str(path))
