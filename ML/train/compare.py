"""
compare.py — Canopy-based vegetation change analysis between two images.

This is a thin reporting + visualization wrapper around the canonical
pipeline in core/pipeline.py, so it runs the EXACT same code path that
validation/metrics.py grades.

Pipeline (all stages handled by core/pipeline.py)
-------------------------------------------------
1. Registration       — AKAZE + RANSAC homography
2. Preprocessing      — CLAHE + histogram matching
3. Vegetation mask    — ExG + joint Otsu (or HSV legacy with --no-exg)
4. YOLO cross-check   — optional (--use-yolo), slow
5. Change-zone diff   — min_zone_px filter applied to masks + zones

Usage
-----
    python compare.py before.jpg after.jpg
    python compare.py before.jpg after.jpg --scale 0.05 --biome temperate
    python compare.py before.jpg after.jpg --use-yolo --conf 0.3
    python compare.py before.jpg after.jpg --no-registration --no-exg   # legacy-ish
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# ── Make core/ and train/ importable regardless of CWD ───────────────────────
_THIS_DIR     = Path(__file__).resolve().parent          # train/
_PROJECT_ROOT = _THIS_DIR.parent
_CORE_DIR     = _PROJECT_ROOT / "core"
sys.path.insert(0, str(_CORE_DIR))
sys.path.insert(0, str(_THIS_DIR))

from pipeline import compare_pipeline, load_yolo          # noqa: E402
from canopy   import compute_metrics                      # noqa: E402

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MODEL_PATH = str(_THIS_DIR / "runs" / "detect" / "runs" / "tree_detect" /
                 "yolo26m_trees-8" / "weights" / "best.pt")

# Approximate CO2 sequestration rate per m² of canopy per year (kg).
# Defensible mid-range values; vary ±50 % by species, age, climate.
BIOME_CO2 = {
    'temperate':     0.7,
    'tropical':      1.2,
    'boreal':        0.4,
    'mediterranean': 0.5,
}

LOSS_ZONE_MIN_PX = 500

# ─── Environmental-estimate constants (APPROXIMATE — edit to taste) ─────────────
# IMPORTANT: every physical figure (m², CO2, O2, biomass) depends on the
# real-world size of a pixel. Pass --scale (metres per pixel) for real numbers.
# If omitted, we fall back to this assumed scale and label everything "EST."
DEFAULT_SCALE_M_PER_PX     = 0.05    # ~5 cm/px — typical low-altitude drone (ASSUMED)

AVG_TREE_CROWN_M2          = 25.0    # mean mature-tree crown area, mixed species
CARBON_STOCK_KG_CO2_PER_M2 = 30.0    # standing carbon stored per m² canopy (CO2-equiv)
O2_PER_CO2_RATIO           = 32.0 / 44.0   # photosynthesis stoichiometry
CAR_CO2_KG_PER_YEAR        = 4600.0  # avg passenger vehicle/year (US EPA ≈ 4.6 t)
PERSON_O2_KG_PER_YEAR      = 740.0   # ~0.84 kg O2/person/day
# ────────────────────────────────────────────────────────────────────────────────


def _env_estimates(canopy_m2: float, biome_co2: float) -> dict:
    """Per-image environmental estimates derived from canopy area (m²)."""
    co2_yr = canopy_m2 * biome_co2
    return {
        'trees_est':      canopy_m2 / AVG_TREE_CROWN_M2,
        'co2_seq_kg_yr':  co2_yr,
        'o2_kg_yr':       co2_yr * O2_PER_CO2_RATIO,
        'carbon_stock_kg_co2': canopy_m2 * CARBON_STOCK_KG_CO2_PER_M2,
    }


# ── Visualisation helpers ─────────────────────────────────────────────────────

def _overlay(img: np.ndarray, mask: np.ndarray,
             color: tuple, alpha: float = 0.4) -> np.ndarray:
    """Tint pixels where ``mask`` is set with ``color`` at ``alpha``."""
    out = img.copy()
    layer = np.zeros_like(img); layer[:] = color
    sel = mask > 0
    out[sel] = (img[sel].astype(np.float32) * (1 - alpha) +
                layer[sel].astype(np.float32) * alpha).astype(np.uint8)
    return out


def _draw_zones(img: np.ndarray, zones: list,
                color: tuple, label_prefix: str) -> np.ndarray:
    out = img.copy()
    for i, z in enumerate(zones, 1):
        x1, y1, x2, y2 = z['bbox']
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{label_prefix}{i}: {z['area_px']:,}px"
        cv2.putText(out, label, (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, label, (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return out


def _make_header(text: str, width: int, height: int = 30) -> np.ndarray:
    bar = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(bar, text, (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return bar


def _add_legend(img: np.ndarray) -> np.ndarray:
    w = img.shape[1]
    bar = np.full((40, w, 3), 30, dtype=np.uint8)
    items = [
        ((0, 200, 0),   "Canopy (validated)"),
        ((0, 100, 255), "Loss zone"),
        ((0, 200, 200), "Growth zone"),
    ]
    x = 10
    for bgr, label in items:
        cv2.rectangle(bar, (x, 10), (x + 20, 30), bgr, -1)
        cv2.putText(bar, label, (x + 25, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)
        x += 240
    return np.vstack([img, bar])


# ── Main comparison ───────────────────────────────────────────────────────────

SEG_MODEL_PATH = str(_PROJECT_ROOT / "models" / "tree_seg.pt")


def _to_native(v):
    """Recursively convert numpy scalars to Python native types for JSON serialisation."""
    if hasattr(v, 'item'):
        return v.item()
    if isinstance(v, dict):
        return {k: _to_native(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_native(x) for x in v]
    return v


def compare(before_path: str, after_path: str,
            conf: float = 0.25,
            scale_m_per_px: float = None,
            biome: str = 'temperate',
            min_zone_px: int = LOSS_ZONE_MIN_PX,
            save: bool = True,
            use_registration: bool = True,
            use_preprocessing: bool = True,
            use_exg: bool = True,
            use_yolo: bool = False,
            vegetation_source: str = None,
            seg_model_path: str = SEG_MODEL_PATH,
            json_output: bool = False) -> dict:

    for p in (before_path, after_path):
        if not Path(p).exists():
            print(f"Error: image not found — {p}")
            sys.exit(1)

    biome_co2 = BIOME_CO2.get(biome, BIOME_CO2['temperate'])

    # Physical figures need a real-world pixel size. If --scale wasn't given,
    # fall back to an ASSUMED scale and flag every derived number as an estimate.
    scale_assumed = scale_m_per_px is None
    eff_scale     = scale_m_per_px if scale_m_per_px is not None else DEFAULT_SCALE_M_PER_PX

    model = None
    if use_yolo:
        print(f"Loading YOLO model: {MODEL_PATH}")
        model = load_yolo(MODEL_PATH)

    seg_model = None
    if vegetation_source == "seg":
        print(f"Loading seg model: {seg_model_path}")
        seg_model = load_yolo(seg_model_path)

    print(f"\nComparing\n  BEFORE: {before_path}\n  AFTER : {after_path}")
    result = compare_pipeline(
        before_path, after_path,
        use_registration=use_registration,
        use_preprocessing=use_preprocessing,
        vegetation_source=vegetation_source,
        use_exg=use_exg,
        seg_model=seg_model,
        use_yolo=use_yolo,
        yolo_model=model,
        conf=conf,
        min_zone_px=min_zone_px,
    )

    h_b, w_b = result.before.shape[:2]

    # Confirmed-tree counts only exist when YOLO ran
    conf_b = result.yolo.get("confirmed_before", 0) if use_yolo else 0
    conf_a = result.yolo.get("confirmed_after",  0) if use_yolo else 0

    m_before = compute_metrics(result.canopy_before, conf_b,
                               eff_scale, biome_co2)
    m_after  = compute_metrics(result.canopy_after,  conf_a,
                               eff_scale, biome_co2)
    env_before = _env_estimates(m_before['canopy_m2'], biome_co2)
    env_after  = _env_estimates(m_after['canopy_m2'],  biome_co2)

    # ── Console report ───────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"  VEGETATION CHANGE REPORT  (biome: {biome})")
    print("=" * 72)

    # Pipeline configuration line so the report is self-documenting
    stages = []
    stages.append("reg"     if result.registration.get("used")  else "no-reg")
    stages.append("prep"    if result.preprocessing.get("used") else "no-prep")
    stages.append(result.vegetation.get("method", "?"))
    stages.append("yolo"    if result.yolo.get("used")          else "no-yolo")
    print(f"  Pipeline: {' | '.join(stages)}   "
          f"(min_zone_px={min_zone_px}, {result.elapsed_s:.1f}s)")
    if result.registration.get("used"):
        print(f"  Registration: {'OK' if result.registration.get('success') else 'FAILED → identity'}"
              f"  ({result.registration.get('n_inliers', 0)} inliers)")
    print("=" * 72)

    def _row(label, kb, ka, fmt='{:>14,.0f}'):
        delta = ka - kb
        sign  = '+' if delta > 0 else ''
        print(f"  {label:<28}{fmt.format(kb)}{fmt.format(ka)}   {sign}{fmt.format(delta).strip()}")

    print(f"  {'':<28}{'BEFORE':>14}{'AFTER':>14}   DELTA")
    print("  " + "-" * 70)
    if use_yolo:
        _row('Confirmed trees', m_before['confirmed_trees'], m_after['confirmed_trees'])
    _row('Canopy pixels', m_before['canopy_pixels'], m_after['canopy_pixels'])
    _row('Canopy %',      m_before['canopy_pct'],    m_after['canopy_pct'], fmt='{:>14.2f}')

    est_tag = " (EST)" if scale_assumed else ""
    _row(f'Canopy m²{est_tag}',         m_before['canopy_m2'],         m_after['canopy_m2'],         fmt='{:>14,.1f}')
    _row(f'CO2 kg/year (seq){est_tag}', m_before['co2_kg_per_year'],   m_after['co2_kg_per_year'],   fmt='{:>14,.1f}')
    _row(f'O2  kg/year{est_tag}',       m_before['o2_kg_per_year'],    m_after['o2_kg_per_year'],    fmt='{:>14,.1f}')
    _row(f'Est. trees{est_tag}',        env_before['trees_est'],       env_after['trees_est'],       fmt='{:>14,.0f}')
    _row(f'Stored carbon kg CO2e{est_tag}',
         env_before['carbon_stock_kg_co2'], env_after['carbon_stock_kg_co2'], fmt='{:>14,.0f}')

    # ── Net change impact (the headline number for deforestation monitoring) ─
    canopy_delta_m2 = m_after['canopy_m2'] - m_before['canopy_m2']
    seq_delta_kg    = env_after['co2_seq_kg_yr']        - env_before['co2_seq_kg_yr']
    o2_delta_kg     = env_after['o2_kg_yr']             - env_before['o2_kg_yr']
    stock_delta_kg  = env_after['carbon_stock_kg_co2']  - env_before['carbon_stock_kg_co2']
    sign  = lambda v: '+' if v >= 0 else ''
    verb  = "GAINED" if canopy_delta_m2 >= 0 else "LOST"
    print()
    print(f"  ── Net change impact{est_tag} ──")
    print(f"    Canopy area {verb:<6}: {sign(canopy_delta_m2)}{canopy_delta_m2:,.1f} m²")
    print(f"    Annual CO2 sequestration change: {sign(seq_delta_kg)}{seq_delta_kg:,.1f} kg/yr")
    print(f"    Annual O2 production change    : {sign(o2_delta_kg)}{o2_delta_kg:,.1f} kg/yr")
    print(f"    Standing-carbon change (CO2e)  : {sign(stock_delta_kg)}{stock_delta_kg:,.1f} kg")
    # Relatable equivalents (magnitude only)
    abs_seq = abs(seq_delta_kg)
    abs_o2  = abs(o2_delta_kg)
    if abs_seq > 1:
        print(f"    ≈ {abs_seq / CAR_CO2_KG_PER_YEAR:,.1f} avg cars' annual emissions"
              f" ({'offset' if seq_delta_kg >= 0 else 'no longer offset'})")
    if abs_o2 > 1:
        print(f"    ≈ O2 for {abs_o2 / PERSON_O2_KG_PER_YEAR:,.1f} people for a year"
              f" ({'gained' if o2_delta_kg >= 0 else 'lost'})")

    if scale_assumed:
        print()
        print(f"  ⚠ Scale was ASSUMED ({DEFAULT_SCALE_M_PER_PX} m/px). Pass --scale "
              f"<m/px> for real values; physical figures here are order-of-magnitude only.")

    print()
    print(f"  Loss zones   (≥ {min_zone_px}px): {len(result.loss_zones)}")
    for i, z in enumerate(result.loss_zones[:10], 1):
        extra = ""
        if eff_scale is not None:
            m2 = z['area_px'] * (eff_scale ** 2)
            extra = f"  ≈ {m2:,.1f} m²  ≈ {m2 * biome_co2:,.1f} kg CO2/yr lost"
        print(f"    L{i}  area {z['area_px']:>8,} px  centroid ({z['cx']:.0f}, {z['cy']:.0f}){extra}")

    print(f"  Growth zones (≥ {min_zone_px}px): {len(result.growth_zones)}")
    for i, z in enumerate(result.growth_zones[:10], 1):
        extra = ""
        if eff_scale is not None:
            m2 = z['area_px'] * (eff_scale ** 2)
            extra = f"  ≈ {m2:,.1f} m²  ≈ {m2 * biome_co2:,.1f} kg CO2/yr gained"
        print(f"    G{i}  area {z['area_px']:>8,} px  centroid ({z['cx']:.0f}, {z['cy']:.0f}){extra}")

    if not result.loss_zones and not result.growth_zones:
        print("  No significant change zones detected at the given threshold.")

    # ── Assumptions used (transparency — edit constants in compare.py) ──
    print()
    print("  ── Assumptions ──")
    print(f"    Scale                : {eff_scale} m/px"
          f"{'  (ASSUMED — pass --scale for real)' if scale_assumed else '  (from --scale)'}")
    print(f"    Biome CO2 rate       : {biome_co2} kg CO2/m²/yr  ({biome})")
    print(f"    Mean tree crown area : {AVG_TREE_CROWN_M2} m²  (mixed species)")
    print(f"    Stored carbon density: {CARBON_STOCK_KG_CO2_PER_M2} kg CO2e/m²  (canopy)")
    print(f"    Car equivalence      : {CAR_CO2_KG_PER_YEAR:,.0f} kg CO2/yr per avg vehicle")
    print(f"    Person O2            : {PERSON_O2_KG_PER_YEAR:,.0f} kg O2/yr per person")

    print("=" * 72 + "\n")

    # ── Composite visualisation ──────────────────────────────────────────────
    if save:
        vis_b = _overlay(result.before, result.canopy_before,
                         color=(0, 200, 0), alpha=0.35)

        vis_a = _overlay(result.after, result.canopy_after,
                         color=(0, 200, 0), alpha=0.35)
        vis_a = _overlay(vis_a, result.loss_mask,   color=(0, 100, 255), alpha=0.55)
        vis_a = _overlay(vis_a, result.growth_mask, color=(0, 200, 200), alpha=0.55)
        vis_a = _draw_zones(vis_a, result.loss_zones,   (0, 100, 255), 'L')
        vis_a = _draw_zones(vis_a, result.growth_zones, (0, 200, 200), 'G')

        tree_b = f"{m_before['confirmed_trees']} trees, " if use_yolo else ""
        tree_a = f"{m_after['confirmed_trees']} trees, "  if use_yolo else ""
        head_b = _make_header(
            f"BEFORE  ({tree_b}{m_before['canopy_pct']:.1f}% canopy)", w_b)
        head_a = _make_header(
            f"AFTER   ({tree_a}{m_after['canopy_pct']:.1f}% canopy)", w_b)
        col_b = np.vstack([head_b, vis_b])
        col_a = np.vstack([head_a, vis_a])

        composite = _add_legend(np.hstack([col_b, col_a]))

        out_dir = _THIS_DIR / "results"; out_dir.mkdir(exist_ok=True)
        stem_b = Path(before_path).stem
        stem_a = Path(after_path).stem
        src_tag = (result.vegetation.get("method", "veg")
                   .replace(" ", "").replace("/", ""))
        out_path = out_dir / f"compare_{stem_b}_vs_{stem_a}_{src_tag}.jpg"
        cv2.imwrite(str(out_path), composite)
        print(f"Comparison image saved to: {out_path}")

    ret = {
        'metrics_before': m_before,
        'metrics_after':  m_after,
        'loss_zones':     result.loss_zones,
        'growth_zones':   result.growth_zones,
        'diagnostics': {
            'registration':  result.registration,
            'preprocessing': result.preprocessing,
            'vegetation':    result.vegetation,
            'yolo':          result.yolo,
            'elapsed_s':     result.elapsed_s,
        },
    }

    if json_output:
        import json
        payload = _to_native({
            'metrics_before': m_before,
            'metrics_after':  m_after,
            'env_before':     env_before,
            'env_after':      env_after,
            'canopy_delta_m2':  canopy_delta_m2,
            'seq_delta_kg':     seq_delta_kg,
            'o2_delta_kg':      o2_delta_kg,
            'stock_delta_kg':   stock_delta_kg,
            'loss_zones': [
                {'area_px': z['area_px'], 'cx': float(z['cx']), 'cy': float(z['cy'])}
                for z in result.loss_zones
            ],
            'growth_zones': [
                {'area_px': z['area_px'], 'cx': float(z['cx']), 'cy': float(z['cy'])}
                for z in result.growth_zones
            ],
            'scale_assumed': scale_assumed,
            'biome':         biome,
            'elapsed_s':     result.elapsed_s,
            'veg_method':    result.vegetation.get('method', ''),
        })
        print("JSON_OUTPUT:" + json.dumps(payload))

    return ret


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vegetation change analysis (core/pipeline.py engine)."
    )
    parser.add_argument("before",        help="Path to the BEFORE (baseline) image")
    parser.add_argument("after",         help="Path to the AFTER image")
    parser.add_argument("--conf",        type=float, default=0.25,
                        help="YOLO confidence threshold (default: 0.25)")
    parser.add_argument("--scale",       type=float, default=None,
                        help="Meters per pixel (e.g. 0.05 = 5 cm/px). "
                             "Without it, only relative metrics are reported.")
    parser.add_argument("--biome",       choices=list(BIOME_CO2.keys()),
                        default='temperate',
                        help="Biome → CO2 rate constant (default: temperate)")
    parser.add_argument("--min-zone-px", type=int, default=LOSS_ZONE_MIN_PX,
                        help=f"Min connected-component size for a change zone "
                             f"(default: {LOSS_ZONE_MIN_PX})")
    parser.add_argument("--use-yolo",    action="store_true",
                        help="Enable YOLO cross-validation (slower, "
                             "marginal accuracy gain; off by default)")
    parser.add_argument("--no-registration",  action="store_true",
                        help="Skip AKAZE+RANSAC image registration")
    parser.add_argument("--no-preprocessing", action="store_true",
                        help="Skip CLAHE + histogram matching")
    parser.add_argument("--no-exg",      action="store_true",
                        help="Use legacy HSV threshold instead of ExG+Otsu")
    parser.add_argument("--veg-source",  choices=("exg", "hsv", "seg"),
                        default=None,
                        help="Vegetation mask source: exg (default, production), "
                             "hsv (legacy), or seg (EXPERIMENTAL — only works on "
                             "imagery like its training set; does not generalize)")
    parser.add_argument("--seg-model",   default=SEG_MODEL_PATH,
                        help="Path to the YOLO-seg model (for --veg-source seg)")
    parser.add_argument("--no-save",     action="store_true",
                        help="Don't save the composite comparison image")
    parser.add_argument("--json-output", action="store_true",
                        help="Print structured JSON metrics to stdout (prefixed JSON_OUTPUT:)")
    args = parser.parse_args()

    veg_source = args.veg_source or ("hsv" if args.no_exg else None)

    compare(
        args.before,
        args.after,
        conf=args.conf,
        scale_m_per_px=args.scale,
        biome=args.biome,
        min_zone_px=args.min_zone_px,
        save=not args.no_save,
        use_registration=not args.no_registration,
        use_preprocessing=not args.no_preprocessing,
        use_exg=not args.no_exg,
        use_yolo=args.use_yolo,
        vegetation_source=veg_source,
        seg_model_path=args.seg_model,
        json_output=args.json_output,
    )
