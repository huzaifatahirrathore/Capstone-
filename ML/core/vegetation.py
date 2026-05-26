"""
vegetation.py — Continuous vegetation indices + adaptive (Otsu) thresholding.

Why this exists
---------------
The HSV canopy mask in train/canopy.py uses fixed thresholds (H ∈ 25..95,
S/V > 30). Validation shows that's brittle:
  • 100% false-positive rate on `lighting` pairs (small hue/sat shifts flip
    pixels in/out of the green band)
  • Boundary flicker after registration (sub-pixel interpolation moves
    pixels across the hard threshold)

Vegetation indices like ExG produce a CONTINUOUS-valued "greenness" score
per pixel. Combined with Otsu's adaptive thresholding, that gives masks
that are far more stable across lighting, registration artifacts, and
minor color shifts.

Available indices
-----------------
  ExG   (Excess Green)              : 2G − R − B            Woebbecke 1995
  ExGR  (ExG minus Excess Red)      : 3G − 2.4R − B         Meyer & Camargo Neto 2008
  CIVE  (Color Index of Vegetation) : 0.441R − 0.811G + 0.385B + 18.78745
                                      (negated so higher = more vegetation)
  VARI  (Visible Atmospheric Resist): (G − R) / (G + R − B)

Drop-in compatibility
---------------------
`extract_vegetation_mask(bgr) -> uint8 mask` is a drop-in replacement for
`canopy.extract_canopy_mask`: same input/output, same morphology cleanup.

Usage (library)
---------------
    from core.vegetation import extract_vegetation_mask
    mask = extract_vegetation_mask(img_bgr)

    # With diagnostics:
    from core.vegetation import extract_vegetation_mask_with_info
    mask, info = extract_vegetation_mask_with_info(img, method='ExGR')

Usage (CLI)
-----------
    python -m core.vegetation image.jpg
    python -m core.vegetation image.jpg --method ExGR
    python -m core.vegetation image.jpg --debug-vis vis.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


# ─── DEFAULTS ─────────────────────────────────────────────────────────────────
DEFAULT_METHOD    = "ExG"
MIN_BLOB_PIXELS   = 100             # drop isolated specks
MORPH_KERNEL_SIZE = 5
AVAILABLE_INDICES = ("ExG", "ExGR", "CIVE", "VARI")


# ─── VEGETATION INDEX FUNCTIONS ───────────────────────────────────────────────

def excess_green(img_bgr: np.ndarray) -> np.ndarray:
    """ExG = 2G − R − B  (Woebbecke 1995). Returns int16 (can be negative)."""
    img = img_bgr.astype(np.int16)
    B, G, R = cv2.split(img)
    return (2 * G - R - B).astype(np.int16)


def excess_green_minus_red(img_bgr: np.ndarray) -> np.ndarray:
    """ExGR = ExG − ExR = 3G − 2.4R − B  (Meyer & Camargo Neto 2008)."""
    img = img_bgr.astype(np.float32)
    B, G, R = cv2.split(img)
    return 3.0 * G - 2.4 * R - B


def cive(img_bgr: np.ndarray) -> np.ndarray:
    """
    CIVE (Color Index of Vegetation Extraction).
    Original formula: 0.441R − 0.811G + 0.385B + 18.78745
    (low = vegetation). We NEGATE so higher = more vegetation, consistent
    with the other indices and with Otsu's "above threshold = positive" sense.
    """
    img = img_bgr.astype(np.float32)
    B, G, R = cv2.split(img)
    return -(0.441 * R - 0.811 * G + 0.385 * B + 18.78745)


def vari(img_bgr: np.ndarray) -> np.ndarray:
    """VARI = (G − R) / (G + R − B). Range typically ≈ [−1, 1]."""
    img = img_bgr.astype(np.float32)
    B, G, R = cv2.split(img)
    denom = G + R - B
    denom = np.where(np.abs(denom) < 1e-3, 1e-3, denom)
    return (G - R) / denom


_INDEX_DISPATCH = {
    "ExG":  excess_green,
    "ExGR": excess_green_minus_red,
    "CIVE": cive,
    "VARI": vari,
}


def vegetation_index(img_bgr: np.ndarray,
                     method: str = DEFAULT_METHOD) -> np.ndarray:
    """Compute the requested vegetation index. Returns float32 array."""
    if method not in _INDEX_DISPATCH:
        raise ValueError(f"Unknown method '{method}'. "
                         f"Available: {AVAILABLE_INDICES}")
    return _INDEX_DISPATCH[method](img_bgr).astype(np.float32)


def normalize_index(idx: np.ndarray) -> np.ndarray:
    """Linearly map any-range index to uint8 [0, 255] for thresholding."""
    lo, hi = float(idx.min()), float(idx.max())
    if hi - lo < 1e-6:
        return np.zeros_like(idx, dtype=np.uint8)
    return ((idx - lo) / (hi - lo) * 255.0).astype(np.uint8)


# ─── DIAGNOSTICS ──────────────────────────────────────────────────────────────

@dataclass
class VegetationMaskInfo:
    method:          str
    otsu_threshold:  int      # in normalized 0–255 space
    raw_threshold:   float    # in the index's native units
    pre_fraction:    float    # vegetation fraction before morphology cleanup
    final_fraction:  float    # after morphology + size filter

    def to_dict(self) -> dict:
        return {
            "method":          self.method,
            "otsu_threshold":  int(self.otsu_threshold),
            "raw_threshold":   float(self.raw_threshold),
            "pre_fraction":    float(self.pre_fraction),
            "final_fraction":  float(self.final_fraction),
        }


# ─── CLEANUP ──────────────────────────────────────────────────────────────────

def _clean_mask(mask: np.ndarray, *,
                min_blob_pixels: int,
                apply_morphology: bool) -> np.ndarray:
    """Morphological open + close, then drop small connected components."""
    if apply_morphology:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    if min_blob_pixels > 0:
        n, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask, connectivity=8)
        out = np.zeros_like(mask)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= min_blob_pixels:
                out[labels == i] = 255
        mask = out
    return mask


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def extract_vegetation_mask_with_info(
        img_bgr: np.ndarray, *,
        method: str = DEFAULT_METHOD,
        min_blob_pixels: int = MIN_BLOB_PIXELS,
        apply_morphology: bool = True,
) -> tuple[np.ndarray, VegetationMaskInfo]:
    """
    Full pipeline: vegetation index → Otsu → morphology → size filter.

    Returns (binary_mask_uint8, info).
    """
    if img_bgr is None or img_bgr.size == 0:
        raise ValueError("extract_vegetation_mask: empty input")

    idx = vegetation_index(img_bgr, method=method)
    idx8 = normalize_index(idx)

    otsu_t, raw_mask = cv2.threshold(
        idx8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pre_fraction = float((raw_mask > 0).sum()) / raw_mask.size

    final = _clean_mask(raw_mask,
                        min_blob_pixels=min_blob_pixels,
                        apply_morphology=apply_morphology)
    final_fraction = float((final > 0).sum()) / final.size

    # Map otsu_t (uint8 normalized) back to the index's own units
    lo, hi = float(idx.min()), float(idx.max())
    raw_t = lo + (otsu_t / 255.0) * (hi - lo)

    info = VegetationMaskInfo(
        method=method,
        otsu_threshold=int(otsu_t),
        raw_threshold=float(raw_t),
        pre_fraction=pre_fraction,
        final_fraction=final_fraction,
    )
    return final, info


def extract_vegetation_mask(
        img_bgr: np.ndarray, *,
        method: str = DEFAULT_METHOD,
        min_blob_pixels: int = MIN_BLOB_PIXELS,
        apply_morphology: bool = True,
) -> np.ndarray:
    """
    Drop-in replacement for `canopy.extract_canopy_mask`.

    Returns just the binary mask (uint8, 0/255). The signature matches
    the HSV version so it can be swapped at the call site with no other
    changes.
    """
    mask, _ = extract_vegetation_mask_with_info(
        img_bgr, method=method,
        min_blob_pixels=min_blob_pixels,
        apply_morphology=apply_morphology,
    )
    return mask


def extract_vegetation_masks_paired(
        before_bgr: np.ndarray, after_bgr: np.ndarray, *,
        method: str = DEFAULT_METHOD,
        min_blob_pixels: int = MIN_BLOB_PIXELS,
        apply_morphology: bool = True,
) -> tuple[np.ndarray, np.ndarray, VegetationMaskInfo, VegetationMaskInfo]:
    """
    Compute vegetation masks for a registered before/after pair using a
    SHARED Otsu threshold derived from their combined pixel distribution.

    This eliminates the "per-image Otsu drift" problem: when the two
    images differ slightly (JPEG noise, interpolation), per-image Otsu
    can pick different thresholds and produce phantom change at every
    canopy boundary. A joint threshold guarantees both masks are
    quantized identically, so only real differences in the index values
    survive the diff.

    Returns (mask_before, mask_after, info_before, info_after) — both
    info dicts report the same shared otsu_threshold.
    """
    if before_bgr is None or after_bgr is None:
        raise ValueError("extract_vegetation_masks_paired: both images required")

    idx_b = vegetation_index(before_bgr, method=method)
    idx_a = vegetation_index(after_bgr,  method=method)

    # Joint normalization range so both maps share the same uint8 scale
    lo = float(min(idx_b.min(), idx_a.min()))
    hi = float(max(idx_b.max(), idx_a.max()))
    span = hi - lo if hi - lo > 1e-6 else 1.0

    idx_b8 = ((idx_b - lo) / span * 255.0).astype(np.uint8)
    idx_a8 = ((idx_a - lo) / span * 255.0).astype(np.uint8)

    # Joint Otsu over the concatenated histograms
    joint = np.concatenate([idx_b8.ravel(), idx_a8.ravel()])
    otsu_t, _ = cv2.threshold(joint, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    raw_t = lo + (otsu_t / 255.0) * span

    # Apply the SAME threshold to both images
    raw_mask_b = (idx_b8 >= otsu_t).astype(np.uint8) * 255
    raw_mask_a = (idx_a8 >= otsu_t).astype(np.uint8) * 255

    pre_b = float((raw_mask_b > 0).sum()) / raw_mask_b.size
    pre_a = float((raw_mask_a > 0).sum()) / raw_mask_a.size

    final_b = _clean_mask(raw_mask_b, min_blob_pixels=min_blob_pixels,
                          apply_morphology=apply_morphology)
    final_a = _clean_mask(raw_mask_a, min_blob_pixels=min_blob_pixels,
                          apply_morphology=apply_morphology)

    info_b = VegetationMaskInfo(
        method=method, otsu_threshold=int(otsu_t), raw_threshold=float(raw_t),
        pre_fraction=pre_b,
        final_fraction=float((final_b > 0).sum()) / final_b.size,
    )
    info_a = VegetationMaskInfo(
        method=method, otsu_threshold=int(otsu_t), raw_threshold=float(raw_t),
        pre_fraction=pre_a,
        final_fraction=float((final_a > 0).sum()) / final_a.size,
    )
    return final_b, final_a, info_b, info_a


def continuous_change_masks(
        before_bgr: np.ndarray, after_bgr: np.ndarray, *,
        method: str = DEFAULT_METHOD,
        min_delta: int = 40,
        min_blob_pixels: int = MIN_BLOB_PIXELS,
        apply_morphology: bool = True,
) -> dict:
    """
    Continuous-value change detection for a registered before/after pair.

    Binary mask diffing flags a pixel whenever it crosses the vegetation
    threshold — so tiny near-threshold wobble (lighting, JPEG, registration
    resampling) shows up as phantom change. Instead, this flags a pixel as
    loss/growth only when it BOTH crosses the joint-Otsu threshold AND its
    index value changes by at least ``min_delta`` (on the 0–255 scale). That
    rejects edge flicker while keeping genuine, large changes.

    ``min_delta=0`` reproduces the plain binary diff exactly (any threshold
    crossing has a positive delta), so this is a strict superset.

    Returns a dict with:
        canopy_before, canopy_after : cleaned binary masks (for display/metrics)
        loss_mask, growth_mask      : uint8 0/255 change masks
        otsu_threshold              : shared threshold (0–255)
        min_delta                   : the magnitude gate used
    """
    if before_bgr is None or after_bgr is None:
        raise ValueError("continuous_change_masks: both images required")

    idx_b = vegetation_index(before_bgr, method=method)
    idx_a = vegetation_index(after_bgr,  method=method)

    lo = float(min(idx_b.min(), idx_a.min()))
    hi = float(max(idx_b.max(), idx_a.max()))
    span = hi - lo if hi - lo > 1e-6 else 1.0
    b8 = ((idx_b - lo) / span * 255.0).astype(np.uint8)
    a8 = ((idx_a - lo) / span * 255.0).astype(np.uint8)

    joint = np.concatenate([b8.ravel(), a8.ravel()])
    otsu_t, _ = cv2.threshold(joint, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    veg_b = b8 >= otsu_t
    veg_a = a8 >= otsu_t
    delta = b8.astype(np.int16) - a8.astype(np.int16)   # +ve = vegetation dropped

    loss   = veg_b & (~veg_a) & (delta      >= min_delta)
    growth = (~veg_b) & veg_a & ((-delta)    >= min_delta)

    # Light morphology to de-speckle; size filtering happens later (min_zone_px).
    loss_mask   = _clean_mask((loss   * 255).astype(np.uint8),
                              min_blob_pixels=0, apply_morphology=apply_morphology)
    growth_mask = _clean_mask((growth * 255).astype(np.uint8),
                              min_blob_pixels=0, apply_morphology=apply_morphology)

    # Cleaned canopy masks for display / canopy-% metrics.
    canopy_b = _clean_mask((veg_b * 255).astype(np.uint8),
                           min_blob_pixels=min_blob_pixels,
                           apply_morphology=apply_morphology)
    canopy_a = _clean_mask((veg_a * 255).astype(np.uint8),
                           min_blob_pixels=min_blob_pixels,
                           apply_morphology=apply_morphology)

    return {
        "canopy_before":  canopy_b,
        "canopy_after":   canopy_a,
        "loss_mask":      loss_mask,
        "growth_mask":    growth_mask,
        "otsu_threshold": int(otsu_t),
        "min_delta":      int(min_delta),
    }


# ─── DEBUG VISUALIZATION ──────────────────────────────────────────────────────

def make_debug_vis(img_bgr: np.ndarray, *,
                   method: str = DEFAULT_METHOD) -> np.ndarray:
    """2×2 panel: original | index heatmap | Otsu mask | overlay."""
    def _lab(img: np.ndarray, text: str) -> np.ndarray:
        out = img.copy()
        cv2.putText(out, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 255), 1, cv2.LINE_AA)
        return out

    idx = vegetation_index(img_bgr, method=method)
    idx8 = normalize_index(idx)
    heat = cv2.applyColorMap(idx8, cv2.COLORMAP_JET)

    mask, info = extract_vegetation_mask_with_info(img_bgr, method=method)
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    overlay = img_bgr.copy()
    green = np.zeros_like(img_bgr); green[..., 1] = 255
    sel = mask > 0
    overlay[sel] = (overlay[sel].astype(np.float32) * 0.55 +
                    green[sel].astype(np.float32) * 0.45).astype(np.uint8)

    info_text = (f"OTSU MASK  thresh={info.otsu_threshold} "
                 f"  ({info.final_fraction*100:.0f}% veg)")

    top = np.hstack([_lab(img_bgr,  "ORIGINAL"),
                     _lab(heat,     f"{method}  heatmap")])
    bot = np.hstack([_lab(mask_bgr, info_text),
                     _lab(overlay,  "OVERLAY")])
    return np.vstack([top, bot])


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _cli():
    p = argparse.ArgumentParser(
        description="Compute vegetation mask from a continuous index + Otsu",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image",  type=Path)
    p.add_argument("--method", default=DEFAULT_METHOD,
                   choices=AVAILABLE_INDICES,
                   help=f"Index (default: {DEFAULT_METHOD})")
    p.add_argument("--out",       type=Path, default=Path("vegetation_mask.png"))
    p.add_argument("--debug-vis", type=Path, default=None)
    p.add_argument("--min-blob",  type=int,  default=MIN_BLOB_PIXELS)
    p.add_argument("--no-morph",  action="store_true")
    args = p.parse_args()

    img = cv2.imread(str(args.image))
    if img is None:
        sys.exit(f"Cannot read {args.image}")

    mask, info = extract_vegetation_mask_with_info(
        img, method=args.method,
        min_blob_pixels=args.min_blob,
        apply_morphology=not args.no_morph,
    )

    cv2.imwrite(str(args.out), mask)
    print(json.dumps(info.to_dict(), indent=2))
    print(f"\nVegetation mask → {args.out}", file=sys.stderr)

    if args.debug_vis is not None:
        vis = make_debug_vis(img, method=args.method)
        cv2.imwrite(str(args.debug_vis), vis)
        print(f"Debug panel    → {args.debug_vis}", file=sys.stderr)


if __name__ == "__main__":
    _cli()
