"""
registration.py — Feature-based image alignment for vegetation-change detection.

Aligns the `after` image onto the coordinate frame of `before` using AKAZE
features + RANSAC homography. This is the prerequisite for any pixel-level
diff: without it, a small camera-angle shift between two drone passes is
indistinguishable from real vegetation change.

Pipeline
--------
    1. Convert both images to grayscale
    2. AKAZE features + binary descriptors
    3. Brute-force Hamming matching with Lowe's ratio test
    4. RANSAC homography (`cv2.findHomography`)
    5. Reject the homography if it's degenerate (too few inliers,
       extreme determinant, non-finite values)
    6. Warp `after` and a same-shape all-white mask through the homography;
       white pixels in the warped mask mark "valid" pixels — the rest came
       from the constant border and should be ignored by the diff stage

Library usage
-------------
    from core.registration import register

    result = register(before_bgr, after_bgr)
    if result.success:
        aligned = result.aligned_after
        valid  = result.valid_mask
        ...
    else:
        # fall back to unwarped after; result.reason explains why
        ...

CLI usage
---------
    python -m core.registration before.jpg after.jpg
    python -m core.registration before.jpg after.jpg --out aligned.jpg
    python -m core.registration before.jpg after.jpg --debug-vis vis.jpg
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


# ─── QUALITY THRESHOLDS ──────────────────────────────────────────────────────
# These can be overridden via `register(..., min_inliers=...)` etc.

MIN_FEATURES_PER_IMAGE = 50     # below this, AKAZE found too little texture
MIN_RATIO_MATCHES      = 30     # surviving Lowe's ratio test
MIN_INLIERS            = 15     # surviving RANSAC
MIN_INLIER_RATIO       = 0.30   # inliers / total matches

LOWE_RATIO             = 0.75   # standard
RANSAC_REPROJ_THRESH   = 4.0    # pixels

# Reject homographies that warp too aggressively. For aerial drone pairs the
# transform should be close to identity; a 2×2-linear-part determinant far
# from 1 means severe scaling — probably bad correspondences.
MAX_DET_DEVIATION      = 0.40


# ─── RESULT TYPE ──────────────────────────────────────────────────────────────

@dataclass
class RegistrationResult:
    """
    Outcome of a registration attempt.

    On failure (success=False), `aligned_after` falls back to the unwarped
    `after` image (resized to `before`'s shape if needed) and `valid_mask`
    is entirely valid — so the diff stage can still run, just without the
    benefit of alignment. Always check `success` (and `reason`) in callers.
    """
    success:           bool
    reason:            str
    aligned_after:     np.ndarray
    valid_mask:        np.ndarray          # uint8 0/255; 255 = pixel came from real source data
    homography:        Optional[np.ndarray]
    n_features_before: int
    n_features_after:  int
    n_matches:         int
    n_inliers:         int
    inlier_ratio:      float

    def diagnostics(self) -> dict:
        """Lightweight summary safe to log / serialize to JSON."""
        return {
            "success":           bool(self.success),
            "reason":            self.reason,
            "n_features_before": int(self.n_features_before),
            "n_features_after":  int(self.n_features_after),
            "n_matches":         int(self.n_matches),
            "n_inliers":         int(self.n_inliers),
            "inlier_ratio":      float(self.inlier_ratio),
            "homography":        (self.homography.tolist()
                                  if self.homography is not None else None),
        }


# ─── INTERNAL HELPERS ─────────────────────────────────────────────────────────

def _to_gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _ratio_match(desc_a: np.ndarray, desc_b: np.ndarray,
                 ratio: float) -> list:
    """Brute-force Hamming match + Lowe's ratio test (returns list of DMatch)."""
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    knn = matcher.knnMatch(desc_a, desc_b, k=2)
    good = []
    for pair in knn:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio * n.distance:
            good.append(m)
    return good


def _validate_homography(H: np.ndarray) -> tuple[bool, str]:
    """Reject degenerate / overly aggressive transforms."""
    if H is None:
        return False, "no homography"
    if not np.isfinite(H).all():
        return False, "non-finite values in matrix"
    det = abs(float(np.linalg.det(H[:2, :2])))
    if abs(det - 1.0) > MAX_DET_DEVIATION:
        return False, f"linear-part determinant {det:.2f} too far from 1"
    return True, ""


def _fallback_result(after: np.ndarray, target_shape: tuple[int, int],
                     reason: str, *,
                     nfb: int = 0, nfa: int = 0,
                     n_matches: int = 0, n_inliers: int = 0
                     ) -> RegistrationResult:
    """Build a failure result that's still usable: identity alignment."""
    H_dim, W_dim = target_shape
    if after.shape[:2] != target_shape:
        after = cv2.resize(after, (W_dim, H_dim), interpolation=cv2.INTER_AREA)
    return RegistrationResult(
        success=False, reason=reason,
        aligned_after=after,
        valid_mask=np.full((H_dim, W_dim), 255, dtype=np.uint8),
        homography=None,
        n_features_before=nfb, n_features_after=nfa,
        n_matches=n_matches, n_inliers=n_inliers,
        inlier_ratio=(n_inliers / n_matches) if n_matches else 0.0,
    )


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def register(before: np.ndarray, after: np.ndarray, *,
             min_inliers: int = MIN_INLIERS,
             min_inlier_ratio: float = MIN_INLIER_RATIO,
             lowe_ratio: float = LOWE_RATIO,
             reproj_thresh: float = RANSAC_REPROJ_THRESH
             ) -> RegistrationResult:
    """
    Align `after` onto `before`'s coordinate frame.

    Parameters
    ----------
    before, after : BGR images (np.uint8). Must be non-None.
    min_inliers, min_inlier_ratio, lowe_ratio, reproj_thresh :
        Quality thresholds. Defaults match the constants at the top of the
        file; override here if you need to be stricter or looser for a
        specific input domain.

    Returns
    -------
    RegistrationResult — always non-None. Check `success`; on False the
    `aligned_after` field is the unwarped input (resized if needed) so
    callers don't have to special-case it.
    """
    if before is None or after is None:
        raise ValueError("register: both images required")

    target_shape = before.shape[:2]
    H_dim, W_dim = target_shape

    gray_b = _to_gray(before)
    gray_a = _to_gray(after)

    akaze = cv2.AKAZE_create()
    kp_b, desc_b = akaze.detectAndCompute(gray_b, None)
    kp_a, desc_a = akaze.detectAndCompute(gray_a, None)
    nfb, nfa = len(kp_b), len(kp_a)

    if (nfb < MIN_FEATURES_PER_IMAGE or nfa < MIN_FEATURES_PER_IMAGE
            or desc_b is None or desc_a is None):
        return _fallback_result(
            after, target_shape,
            f"too few features (before={nfb}, after={nfa})",
            nfb=nfb, nfa=nfa)

    matches = _ratio_match(desc_a, desc_b, lowe_ratio)
    if len(matches) < MIN_RATIO_MATCHES:
        return _fallback_result(
            after, target_shape,
            f"too few ratio-test matches ({len(matches)})",
            nfb=nfb, nfa=nfa, n_matches=len(matches))

    pts_a = np.float32([kp_a[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    pts_b = np.float32([kp_b[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    H, inlier_mask = cv2.findHomography(pts_a, pts_b, cv2.RANSAC,
                                        reproj_thresh)
    n_inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    inlier_ratio = n_inliers / max(1, len(matches))

    if H is None:
        return _fallback_result(
            after, target_shape, "cv2.findHomography returned None",
            nfb=nfb, nfa=nfa, n_matches=len(matches), n_inliers=n_inliers)

    if n_inliers < min_inliers or inlier_ratio < min_inlier_ratio:
        return _fallback_result(
            after, target_shape,
            f"too few inliers ({n_inliers}, ratio {inlier_ratio:.2f})",
            nfb=nfb, nfa=nfa, n_matches=len(matches), n_inliers=n_inliers)

    ok, why = _validate_homography(H)
    if not ok:
        return _fallback_result(
            after, target_shape, f"invalid homography: {why}",
            nfb=nfb, nfa=nfa, n_matches=len(matches), n_inliers=n_inliers)

    aligned_after = cv2.warpPerspective(
        after, H, (W_dim, H_dim),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # valid-region mask: warp a same-size all-white image so we know which
    # output pixels came from real source vs the constant border.
    white = np.full(after.shape[:2], 255, dtype=np.uint8)
    valid_mask = cv2.warpPerspective(
        white, H, (W_dim, H_dim),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    return RegistrationResult(
        success=True, reason="ok",
        aligned_after=aligned_after,
        valid_mask=valid_mask,
        homography=H,
        n_features_before=nfb,
        n_features_after=nfa,
        n_matches=len(matches),
        n_inliers=n_inliers,
        inlier_ratio=inlier_ratio,
    )


# ─── DEBUG VISUALIZATION ──────────────────────────────────────────────────────

def make_debug_vis(before: np.ndarray, after: np.ndarray,
                   result: RegistrationResult) -> np.ndarray:
    """
    Build a 2×2 panel for visual debugging:

        ┌───────────────┬───────────────┐
        │   BEFORE      │  AFTER (raw)  │
        ├───────────────┼───────────────┤
        │ AFTER aligned │ |before − after|  vs  |before − aligned|
        └───────────────┴───────────────┘

    Useful as `python -m core.registration --debug-vis out.jpg ...`.
    """
    H_dim, W_dim = before.shape[:2]
    after_resized = (after if after.shape[:2] == (H_dim, W_dim)
                     else cv2.resize(after, (W_dim, H_dim)))

    def _label(img: np.ndarray, text: str) -> np.ndarray:
        out = img.copy()
        cv2.putText(out, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 255), 1, cv2.LINE_AA)
        return out

    diff_raw = cv2.absdiff(before, after_resized)
    diff_aln = cv2.absdiff(before, result.aligned_after)
    # boost contrast on the diffs so subtle differences show
    diff_raw = cv2.convertScaleAbs(diff_raw, alpha=3.0)
    diff_aln = cv2.convertScaleAbs(diff_aln, alpha=3.0)

    tl = _label(before,                 "BEFORE")
    tr = _label(after_resized,          "AFTER (raw)")
    bl = _label(result.aligned_after,
                f"AFTER (aligned)  inliers={result.n_inliers}/"
                f"{result.n_matches}")
    br_top = _label(diff_raw, "|before-after|  (no alignment)")
    br_bot = _label(diff_aln, "|before-aligned|  (after alignment)")
    br = np.vstack([br_top, br_bot])
    # Match height of br to tl/tr if needed
    if br.shape[0] != tl.shape[0] * 2:
        br = cv2.resize(br, (tl.shape[1], tl.shape[0] * 2))
    left  = np.vstack([tl, bl])
    right = np.vstack([tr, br[:tl.shape[0]]])
    top   = np.hstack([tl, tr])
    bot   = np.hstack([bl, br[:tl.shape[0]]])
    return np.vstack([top, bot])


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _cli():
    p = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],   # short summary
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("before", type=Path, help="Path to the BEFORE image")
    p.add_argument("after",  type=Path, help="Path to the AFTER image")
    p.add_argument("--out",  type=Path, default=None,
                   help="Where to write the aligned AFTER image "
                        "(default: aligned_<after>.jpg next to the after file)")
    p.add_argument("--debug-vis", type=Path, default=None,
                   help="Optional path to write a side-by-side debug panel")
    p.add_argument("--min-inliers", type=int, default=MIN_INLIERS)
    args = p.parse_args()

    before = cv2.imread(str(args.before))
    after  = cv2.imread(str(args.after))
    if before is None:
        sys.exit(f"Could not read {args.before}")
    if after is None:
        sys.exit(f"Could not read {args.after}")

    result = register(before, after, min_inliers=args.min_inliers)

    print(json.dumps(result.diagnostics(), indent=2))

    if not result.success:
        print(f"\nRegistration FAILED — {result.reason}", file=sys.stderr)
        # We still write the fallback so callers can compare
    out = args.out or args.after.with_name(f"aligned_{args.after.name}")
    cv2.imwrite(str(out), result.aligned_after)
    print(f"\nAligned image → {out}", file=sys.stderr)

    if args.debug_vis is not None:
        vis = make_debug_vis(before, after, result)
        cv2.imwrite(str(args.debug_vis), vis)
        print(f"Debug panel  → {args.debug_vis}", file=sys.stderr)

    sys.exit(0 if result.success else 2)


if __name__ == "__main__":
    _cli()
