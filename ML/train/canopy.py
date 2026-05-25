"""
canopy.py — Vegetation/canopy mask extraction and YOLO cross-validation.

The canopy mask is the primary signal for biomass / CO2 estimation.
YOLO bboxes are used as a secondary validation layer.

Two-way intersection produces four regions:
    confirmed   : YOLO ∩ canopy             (high confidence tree)
    dense       : large canopy without YOLO  (forest interior — kept)
    suspicious  : small canopy without YOLO  (grass / roof — dropped)
    false_pos   : YOLO without canopy        (false positive — dropped)

The validated mask combines confirmed + dense.  Suspicious regions
and false-positive boxes are reported separately so the caller can
display or audit them, but they do not contribute to metrics.
"""

import cv2
import numpy as np


# ── HSV thresholds for vegetation green ──────────────────────────────────────
HSV_GREEN_LOW   = (25,  30,  30)
HSV_GREEN_HIGH  = (95, 255, 255)

# ── Mask cleanup ─────────────────────────────────────────────────────────────
MORPH_KERNEL_SIZE = 5
MIN_BLOB_PIXELS   = 100      # drop isolated specks smaller than this

# ── Cross-validation thresholds ──────────────────────────────────────────────
SUSPICIOUS_MAX_PX = 2000     # canopy region < this without YOLO support → noise
MIN_CANOPY_FILL   = 0.20     # YOLO bbox needs ≥ 20 % canopy inside to be confirmed


# ── Canopy mask extraction ───────────────────────────────────────────────────

def extract_canopy_mask(img_bgr: np.ndarray) -> np.ndarray:
    """
    HSV-based vegetation segmentation.

    Returns a binary uint8 mask (0 or 255) — 255 where the pixel is vegetation.
    Cleanup: morphological open-close + small-component removal.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    raw = cv2.inRange(hsv, np.array(HSV_GREEN_LOW), np.array(HSV_GREEN_HIGH))

    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE))
    cleaned = cv2.morphologyEx(raw,     cv2.MORPH_OPEN,  kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    out = np.zeros_like(cleaned)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= MIN_BLOB_PIXELS:
            out[labels == i] = 255
    return out


# ── Two-way YOLO ↔ canopy validation ─────────────────────────────────────────

def cross_validate(canopy: np.ndarray, yolo_boxes: list) -> dict:
    """
    Cross-validate the canopy mask against YOLO detections.

    Parameters
    ----------
    canopy      : uint8 binary mask (0/255) of vegetation
    yolo_boxes  : list of [x1, y1, x2, y2, conf, cls_id]

    Returns
    -------
    dict with:
        validated         : uint8 mask = confirmed ∪ dense  (used for metrics)
        confirmed_mask    : YOLO ∩ canopy
        dense_mask        : large canopy without YOLO
        suspicious_mask   : small canopy without YOLO  (dropped)
        confirmed_boxes   : YOLO boxes with ≥ MIN_CANOPY_FILL canopy inside
        false_pos_boxes   : YOLO boxes failing the canopy fill check (dropped)
    """
    H, W = canopy.shape

    # Render YOLO boxes into a binary mask
    bbox_mask = np.zeros((H, W), dtype=np.uint8)
    for b in yolo_boxes:
        x1, y1 = max(0, int(b[0])), max(0, int(b[1]))
        x2, y2 = min(W, int(b[2])), min(H, int(b[3]))
        if x2 > x1 and y2 > y1:
            bbox_mask[y1:y2, x1:x2] = 255

    confirmed   = cv2.bitwise_and(canopy, bbox_mask)
    only_canopy = cv2.bitwise_and(canopy, cv2.bitwise_not(bbox_mask))

    # Split canopy-without-YOLO into dense (kept) vs suspicious (dropped)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(only_canopy, connectivity=8)
    dense      = np.zeros((H, W), dtype=np.uint8)
    suspicious = np.zeros((H, W), dtype=np.uint8)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= SUSPICIOUS_MAX_PX:
            dense[labels == i] = 255
        else:
            suspicious[labels == i] = 255

    # Audit each YOLO box for canopy fill
    confirmed_boxes = []
    false_pos_boxes = []
    for b in yolo_boxes:
        x1, y1 = max(0, int(b[0])), max(0, int(b[1]))
        x2, y2 = min(W, int(b[2])), min(H, int(b[3]))
        bbox_area  = max(1, (x2 - x1) * (y2 - y1))
        canopy_in  = int(canopy[y1:y2, x1:x2].sum() // 255)
        if canopy_in / bbox_area >= MIN_CANOPY_FILL:
            confirmed_boxes.append(b)
        else:
            false_pos_boxes.append(b)

    validated = cv2.bitwise_or(confirmed, dense)

    return {
        'validated':       validated,
        'confirmed_mask':  confirmed,
        'dense_mask':      dense,
        'suspicious_mask': suspicious,
        'confirmed_boxes': confirmed_boxes,
        'false_pos_boxes': false_pos_boxes,
    }


# ── Pixel-level change detection ─────────────────────────────────────────────

def compute_change_zones(mask_before: np.ndarray, mask_after: np.ndarray,
                         min_zone_px: int = 500) -> dict:
    """
    Pixel-level delta between two validated canopy masks → connected-component zones.

    Both masks must be the same shape (uint8, 0/255).

    Returns
    -------
    dict with:
        loss_mask    : uint8 mask of pixels that were canopy in BEFORE but not AFTER
        growth_mask  : uint8 mask of pixels that were not canopy in BEFORE but are in AFTER
        loss_zones   : list of dicts {cx, cy, area_px, bbox} sorted by area desc
        growth_zones : same shape as loss_zones
    """
    if mask_before.shape != mask_after.shape:
        raise ValueError(f"Mask shapes differ: {mask_before.shape} vs {mask_after.shape}")

    before_b = mask_before > 0
    after_b  = mask_after  > 0

    loss_mask   = (( before_b & ~after_b) * 255).astype(np.uint8)
    growth_mask = ((~before_b &  after_b) * 255).astype(np.uint8)

    def _zones(mask):
        n, _, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
        out = []
        for i in range(1, n):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < min_zone_px:
                continue
            x, y, w, h = stats[i, 0], stats[i, 1], stats[i, 2], stats[i, 3]
            out.append({
                'cx':      float(cents[i, 0]),
                'cy':      float(cents[i, 1]),
                'area_px': area,
                'bbox':    (int(x), int(y), int(x + w), int(y + h)),
            })
        out.sort(key=lambda z: z['area_px'], reverse=True)
        return out

    return {
        'loss_mask':    loss_mask,
        'growth_mask':  growth_mask,
        'loss_zones':   _zones(loss_mask),
        'growth_zones': _zones(growth_mask),
    }


# ── Biomass / CO2 / O2 metrics ───────────────────────────────────────────────

def compute_metrics(canopy_mask: np.ndarray, confirmed_count: int,
                    scale_m_per_px: float = None,
                    biome_kg_co2_per_m2_year: float = 0.7) -> dict:
    """
    Derive metrics from a validated canopy mask.

    Without ``scale_m_per_px`` only relative metrics are returned (pixels, %).
    With a scale, area_m2 / co2_kg_per_year / o2_kg_per_year are also produced.

    Photosynthesis stoichiometry (6 CO2 + 6 H2O → C6H12O6 + 6 O2) gives an
    O2 mass of CO2_mass × 32/44 ≈ 0.727 × CO2.
    """
    canopy_px  = int((canopy_mask > 0).sum())
    total_px   = int(canopy_mask.size)
    canopy_pct = 100.0 * canopy_px / total_px if total_px else 0.0

    out = {
        'canopy_pixels':   canopy_px,
        'canopy_pct':      canopy_pct,
        'confirmed_trees': confirmed_count,
    }

    if scale_m_per_px is not None and scale_m_per_px > 0:
        area_m2 = canopy_px * (scale_m_per_px ** 2)
        co2     = area_m2 * biome_kg_co2_per_m2_year
        o2      = co2 * (32.0 / 44.0)
        out.update({
            'canopy_m2':       area_m2,
            'co2_kg_per_year': co2,
            'o2_kg_per_year':  o2,
        })

    return out
