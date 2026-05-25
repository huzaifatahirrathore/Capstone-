"""
preprocessing.py — Lighting / color normalization for vegetation change detection.

Background
----------
The HSV canopy mask is fragile to lighting differences between before/after
images: brightness changes, hue shifts, and saturation drift can flip pixels
between "green" and "not green" along canopy edges. The validation harness
shows 100% false-positive rate on `lighting` pairs *even after registration*
because registration aligns geometry, not color.

What this module does
---------------------
Two complementary normalizations, applied in this order:

  1. CLAHE on the L channel (LAB color space) — local contrast equalization
     applied independently to each image. Normalizes within-image variation
     (shadows under one tree shouldn't look brighter than another tree).

  2. Histogram matching of `after` onto `before`, computed from non-vegetation
     pixels only. Aligns the global color distributions between the two
     images. We deliberately exclude vegetation from the CDF computation so
     real vegetation changes don't get "matched away" — we match the
     SURROUNDINGS so the canopy can be compared against an aligned baseline.

If there aren't enough non-vegetation pixels (very dense canopy), the
masked match silently falls back to global matching.

Usage (library)
---------------
    from core.preprocessing import normalize_pair
    before_n, after_n = normalize_pair(before_bgr, after_bgr)

    # Or use individual steps:
    from core.preprocessing import apply_clahe, match_histograms_masked
    eq    = apply_clahe(after)
    fixed = match_histograms_masked(eq, before)

Usage (CLI)
-----------
    python -m core.preprocessing before.jpg after.jpg
    python -m core.preprocessing before.jpg after.jpg --debug-vis vis.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


# ─── DEFAULTS ─────────────────────────────────────────────────────────────────
CLAHE_CLIP_LIMIT     = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)

# HSV vegetation band — matches train/canopy.py so the same notion of "green"
# is used everywhere in the pipeline.
HSV_GREEN_LOW   = (25,  30,  30)
HSV_GREEN_HIGH  = (95, 255, 255)

# If less than this fraction of the image is non-vegetation, masked
# histogram matching falls back to global matching (otherwise the CDF
# is built from too few samples to be reliable).
MIN_REF_FRACTION = 0.05


# ─── DIAGNOSTICS ──────────────────────────────────────────────────────────────

@dataclass
class PreprocessingInfo:
    clahe_applied:           bool
    match_applied:           bool
    match_mode:              str       # "masked" | "global" | "skipped"
    non_vegetation_fraction: float     # of the smaller of before/after

    def to_dict(self) -> dict:
        return {
            "clahe_applied":           bool(self.clahe_applied),
            "match_applied":           bool(self.match_applied),
            "match_mode":              self.match_mode,
            "non_vegetation_fraction": float(self.non_vegetation_fraction),
        }


# ─── CLAHE ────────────────────────────────────────────────────────────────────

def apply_clahe(img_bgr: np.ndarray, *,
                clip_limit: float = CLAHE_CLIP_LIMIT,
                tile_grid: tuple[int, int] = CLAHE_TILE_GRID_SIZE
                ) -> np.ndarray:
    """
    Apply CLAHE to the L channel of LAB color space.

    Operating in LAB rather than BGR preserves chrominance — only
    lightness contrast is equalized. The chroma (a, b) channels are
    left untouched so the green color of vegetation is preserved.
    """
    if img_bgr is None or img_bgr.ndim != 3:
        return img_bgr
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    L_eq = clahe.apply(L)
    return cv2.cvtColor(cv2.merge([L_eq, A, B]), cv2.COLOR_LAB2BGR)


# ─── HISTOGRAM MATCHING (with vegetation exclusion) ───────────────────────────

def _vegetation_mask(img_bgr: np.ndarray) -> np.ndarray:
    """Binary mask of vegetation pixels (HSV green band, matches canopy.py)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, np.array(HSV_GREEN_LOW), np.array(HSV_GREEN_HIGH))


def _build_cdf(channel: np.ndarray,
               mask: Optional[np.ndarray] = None) -> np.ndarray:
    """Cumulative distribution over 256 intensity bins, optionally masked."""
    pixels = channel[mask > 0] if mask is not None else channel.ravel()
    if pixels.size == 0:
        # Pathological: empty mask. Return identity CDF so LUT is a no-op.
        return np.linspace(0.0, 1.0, 256, dtype=np.float64)
    hist = np.bincount(pixels.astype(np.int64), minlength=256).astype(np.float64)
    cdf = hist.cumsum()
    total = cdf[-1]
    return cdf / total if total > 0 else cdf


def _build_lut(src_cdf: np.ndarray, ref_cdf: np.ndarray) -> np.ndarray:
    """For each source intensity, find the ref intensity with matching CDF."""
    # vectorized: for each i, find smallest j such that ref_cdf[j] >= src_cdf[i]
    lut = np.searchsorted(ref_cdf, src_cdf).clip(0, 255).astype(np.uint8)
    return lut


def match_histograms_masked(source: np.ndarray, reference: np.ndarray, *,
                            use_non_vegetation_only: bool = True,
                            min_ref_fraction: float = MIN_REF_FRACTION
                            ) -> tuple[np.ndarray, PreprocessingInfo]:
    """
    Remap `source`'s per-channel intensities so its CDF matches `reference`'s.

    When `use_non_vegetation_only` is True (recommended), the CDF is built
    from non-vegetation pixels only. This prevents real canopy changes from
    being smoothed out: we match the SURROUNDINGS so the canopy can be
    compared against a stable baseline.

    If the non-vegetation coverage in either image is below
    `min_ref_fraction`, the function silently falls back to global matching.
    """
    if source.shape != reference.shape:
        reference = cv2.resize(reference, (source.shape[1], source.shape[0]),
                               interpolation=cv2.INTER_AREA)

    mode = "global"
    src_mask: Optional[np.ndarray] = None
    ref_mask: Optional[np.ndarray] = None
    coverage = 1.0

    if use_non_vegetation_only:
        src_veg = _vegetation_mask(source)
        ref_veg = _vegetation_mask(reference)
        src_nonveg = cv2.bitwise_not(src_veg)
        ref_nonveg = cv2.bitwise_not(ref_veg)

        total_px = source.shape[0] * source.shape[1]
        src_frac = float((src_nonveg > 0).sum()) / total_px
        ref_frac = float((ref_nonveg > 0).sum()) / total_px
        coverage = min(src_frac, ref_frac)

        if coverage >= min_ref_fraction:
            src_mask = src_nonveg
            ref_mask = ref_nonveg
            mode = "masked"
        else:
            mode = "global"

    # Match each BGR channel independently
    src_b, src_g, src_r = cv2.split(source)
    ref_b, ref_g, ref_r = cv2.split(reference)

    def _remap(s, r):
        return cv2.LUT(s, _build_lut(_build_cdf(s, src_mask),
                                     _build_cdf(r, ref_mask)))

    out = cv2.merge([_remap(src_b, ref_b),
                     _remap(src_g, ref_g),
                     _remap(src_r, ref_r)])

    info = PreprocessingInfo(
        clahe_applied=False,
        match_applied=True,
        match_mode=mode,
        non_vegetation_fraction=coverage,
    )
    return out, info


# ─── CONVENIENCE WRAPPER ──────────────────────────────────────────────────────

def normalize_pair(before: np.ndarray, after: np.ndarray, *,
                   apply_clahe_step: bool = True,
                   apply_match_step: bool = True,
                   use_non_vegetation_only: bool = False,
                   ) -> tuple[np.ndarray, np.ndarray, PreprocessingInfo]:
    """
    Apply the full preprocessing pipeline to a registered image pair.

    Returns (before_normalized, after_normalized, info).

    Both images get CLAHE (within-image contrast equalization). Only
    `after` is histogram-matched, with `before` as the reference, so
    the diff stage sees two images that share global color statistics.
    """
    if before is None or after is None:
        raise ValueError("normalize_pair: both images required")

    b, a = before, after
    if apply_clahe_step:
        b = apply_clahe(b)
        a = apply_clahe(a)

    if apply_match_step:
        a, info = match_histograms_masked(
            a, b, use_non_vegetation_only=use_non_vegetation_only)
        info.clahe_applied = apply_clahe_step
    else:
        info = PreprocessingInfo(
            clahe_applied=apply_clahe_step,
            match_applied=False,
            match_mode="skipped",
            non_vegetation_fraction=0.0,
        )

    return b, a, info


# ─── DEBUG VISUALIZATION ──────────────────────────────────────────────────────

def make_debug_vis(before_raw: np.ndarray, after_raw: np.ndarray,
                   before_norm: np.ndarray, after_norm: np.ndarray
                   ) -> np.ndarray:
    """2×2 panel: raw before/after on top, normalized below."""
    def _lab(img: np.ndarray, text: str) -> np.ndarray:
        out = img.copy()
        cv2.putText(out, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 255), 1, cv2.LINE_AA)
        return out

    H, W = before_raw.shape[:2]
    if after_raw.shape[:2] != (H, W):
        after_raw = cv2.resize(after_raw, (W, H))
    if after_norm.shape[:2] != (H, W):
        after_norm = cv2.resize(after_norm, (W, H))
    if before_norm.shape[:2] != (H, W):
        before_norm = cv2.resize(before_norm, (W, H))

    top = np.hstack([_lab(before_raw,  "BEFORE (raw)"),
                     _lab(after_raw,   "AFTER (raw)")])
    bot = np.hstack([_lab(before_norm, "BEFORE (normalized)"),
                     _lab(after_norm,  "AFTER (normalized)")])
    return np.vstack([top, bot])


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _cli():
    p = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("before", type=Path)
    p.add_argument("after",  type=Path)
    p.add_argument("--out-before", type=Path,
                   default=Path("before_normalized.jpg"))
    p.add_argument("--out-after", type=Path,
                   default=Path("after_normalized.jpg"))
    p.add_argument("--debug-vis", type=Path, default=None,
                   help="Path for a 2x2 raw-vs-normalized debug panel")
    p.add_argument("--no-clahe", action="store_true")
    p.add_argument("--no-match", action="store_true")
    p.add_argument("--masked-match", action="store_true",
                   help="Match using non-vegetation pixels only "
                        "(opt-in; safe for urban/mixed scenes, bad for dense canopy)")
    args = p.parse_args()

    b_raw = cv2.imread(str(args.before))
    a_raw = cv2.imread(str(args.after))
    if b_raw is None: sys.exit(f"Cannot read {args.before}")
    if a_raw is None: sys.exit(f"Cannot read {args.after}")

    b_norm, a_norm, info = normalize_pair(
        b_raw, a_raw,
        apply_clahe_step=not args.no_clahe,
        apply_match_step=not args.no_match,
        use_non_vegetation_only=args.masked_match,
    )

    cv2.imwrite(str(args.out_before), b_norm)
    cv2.imwrite(str(args.out_after),  a_norm)
    print(json.dumps(info.to_dict(), indent=2))
    print(f"\nNormalized before → {args.out_before}", file=sys.stderr)
    print(f"Normalized after  → {args.out_after}",  file=sys.stderr)

    if args.debug_vis is not None:
        vis = make_debug_vis(b_raw, a_raw, b_norm, a_norm)
        cv2.imwrite(str(args.debug_vis), vis)
        print(f"Debug panel       → {args.debug_vis}", file=sys.stderr)


if __name__ == "__main__":
    _cli()
