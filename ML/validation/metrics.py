"""
metrics.py — Evaluate the comparison pipeline against synthetic ground truth.

For each pair under `validation/pairs/`:
    1. Run the current comparison pipeline (HSV canopy + YOLO cross-validate
       + change-zone extraction — exactly what compare.py does internally).
    2. Compare the predicted loss/growth masks against the truth masks.
    3. Compute IoU / precision / recall / F1 / area-error for non-empty truth,
       false-positive rate for empty truth.
    4. Aggregate per category, save JSON report, print summary.

The pipeline functions are imported from train/canopy.py directly so we are
measuring the real code, not a copy. Any change to canopy.py is automatically
picked up on the next run.

Usage
-----
    python metrics.py                                # full eval, current pipeline
    python metrics.py --no-yolo                      # HSV-only (skip cross-validation)
    python metrics.py --limit 20                     # quick run on 20 pairs
    python metrics.py --pairs pairs --out reports    # explicit paths
    python metrics.py --conf 0.15                    # different YOLO confidence
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# ─── Import the real pipeline from train/canopy.py + new core modules ────────
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRAIN_DIR    = PROJECT_ROOT / "train"
CORE_DIR     = PROJECT_ROOT / "core"
sys.path.insert(0, str(TRAIN_DIR))
sys.path.insert(0, str(CORE_DIR))

# Single source of truth: grade the SAME pipeline production uses.
from pipeline import compare_pipeline, load_yolo                                     # noqa: E402

# Lazy YOLO import
_YOLO_cls = None
_yolo_model = None

# ─── DEFAULTS (mirror compare.py) ─────────────────────────────────────────────
PAIRS_DEFAULT       = SCRIPT_DIR / "pairs"
REPORTS_DEFAULT     = SCRIPT_DIR / "reports"
YOLO_MODEL_DEFAULT  = (TRAIN_DIR / "runs" / "detect" / "runs" / "tree_detect" /
                       "yolo26m_trees-8" / "weights" / "best.pt")

INFER_IMGSZ         = 1280
INFER_IOU           = 0.6
DEFAULT_CONF        = 0.25
CHANGE_MIN_ZONE_PX  = 500   # default — overridable via --min-zone-px


# ─── PIPELINE WRAPPER ─────────────────────────────────────────────────────────

def _yolo_load(model_path: Path, device: str):
    global _YOLO_cls, _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    if _YOLO_cls is None:
        from ultralytics import YOLO as _Y
        _YOLO_cls = _Y
    if not model_path.exists():
        sys.exit(f"YOLO model not found: {model_path}")
    print(f"Loading YOLO ({device}): {model_path.name}")
    _yolo_model = _YOLO_cls(str(model_path))
    return _yolo_model


def _filter_by_size(mask: np.ndarray, min_size_px: int) -> np.ndarray:
    """
    Drop connected components smaller than `min_size_px`. Matches the
    same logic compute_change_zones uses for its zone list — applying it
    to the raw mask makes min_zone_px actually affect the prediction.
    """
    if min_size_px <= 0:
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = np.zeros_like(mask)
    for i in range(1, n):
        if int(stats[i, cv2.CC_STAT_AREA]) >= min_size_px:
            out[labels == i] = 255
    return out


def _yolo_predict(image, model, device: str, conf: float) -> list:
    """
    `image` may be a Path (file on disk) or a numpy.ndarray (in-memory BGR).
    Returning the in-memory path lets us run YOLO on the *registered* after
    image without writing a temp file.
    """
    source = str(image) if isinstance(image, (str, Path)) else image
    res = model(source, conf=conf, iou=INFER_IOU,
                imgsz=INFER_IMGSZ, device=device, verbose=False)[0]
    return [[*box.xyxy[0].tolist(), box.conf[0].item(), int(box.cls[0].item())]
            for box in res.boxes]


def predict_change(before_path: Path, after_path: Path,
                   *, use_yolo: bool, model, device: str,
                   conf: float,
                   use_registration: bool = True,
                   use_preprocessing: bool = True,
                   use_exg: bool = True,
                   exg_method: str = "ExG",
                   exg_min_delta: int = 20,
                   min_zone_px: int = CHANGE_MIN_ZONE_PX,
                   vegetation_source: Optional[str] = None,
                   seg_model=None,
                   ) -> tuple[np.ndarray, np.ndarray, dict, dict, dict]:
    """
    Thin wrapper over core.pipeline.compare_pipeline so the validation
    harness grades the EXACT code path production uses (no duplicated logic).

    Returns (loss_mask, growth_mask, reg_info, prep_info, veg_info).
    """
    result = compare_pipeline(
        before_path, after_path,
        use_registration=use_registration,
        use_preprocessing=use_preprocessing,
        vegetation_source=vegetation_source,
        use_exg=use_exg,
        exg_method=exg_method,
        exg_min_delta=exg_min_delta,
        seg_model=seg_model,
        use_yolo=use_yolo,
        yolo_model=model,
        device=device,
        conf=conf,
        min_zone_px=min_zone_px,
    )
    return (result.loss_mask, result.growth_mask,
            result.registration, result.preprocessing, result.vegetation)


# ─── PER-MASK METRICS ─────────────────────────────────────────────────────────

def _binary_metrics(pred: np.ndarray, truth: np.ndarray) -> dict:
    """
    Compare two binary masks (uint8 0/255). Returns a dict with every metric.

    Convention for `None` values:
      • iou / precision / recall / f1 / area_error_pct are None when the
        denominator is undefined (typically because truth is empty).
      • false_positive is True iff pred has any positive pixels and truth has none.
    """
    if pred.shape != truth.shape:
        # Should not happen if pairs were generated correctly, but be safe.
        truth = cv2.resize(truth, (pred.shape[1], pred.shape[0]),
                           interpolation=cv2.INTER_NEAREST)

    pb = pred > 0
    tb = truth > 0
    tp = int(np.logical_and(pb, tb).sum())
    fp = int(np.logical_and(pb, np.logical_not(tb)).sum())
    fn = int(np.logical_and(np.logical_not(pb), tb).sum())
    tn = int(np.logical_and(np.logical_not(pb), np.logical_not(tb)).sum())

    pred_px  = int(pb.sum())
    truth_px = int(tb.sum())
    total_px = int(pb.size)

    def _safe_div(num, den):
        return float(num) / float(den) if den > 0 else None

    iou       = _safe_div(tp, tp + fp + fn)
    precision = _safe_div(tp, tp + fp)
    recall    = _safe_div(tp, tp + fn)
    f1        = (2 * precision * recall / (precision + recall)
                 if precision and recall and (precision + recall) > 0
                 else None)

    area_error_pct = (
        abs(pred_px - truth_px) / truth_px * 100.0
        if truth_px > 0 else None
    )

    return {
        "iou":             iou,
        "precision":       precision,
        "recall":          recall,
        "f1":              f1,
        "area_error_pct":  area_error_pct,
        "pred_pixels":     pred_px,
        "truth_pixels":    truth_px,
        "fp_pixels":       fp,
        "fn_pixels":       fn,
        "tp_pixels":       tp,
        "tn_pixels":       tn,
        "false_positive":  bool(pred_px > 0 and truth_px == 0),
        "false_positive_pct": pred_px / total_px * 100.0 if truth_px == 0 else None,
    }


# ─── AGGREGATION ──────────────────────────────────────────────────────────────

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _frac(bools):
    bs = [b for b in bools if b is not None]
    return sum(bs) / len(bs) if bs else None


def aggregate_by_category(per_pair: list[dict]) -> dict:
    """
    Group per-pair metrics by category and produce aggregate statistics.
    Picks the right summary depending on whether truth is empty for the category.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in per_pair:
        groups[p["category"]].append(p)

    summary = {}
    for cat, items in groups.items():
        loss_items   = [it["loss"]   for it in items]
        growth_items = [it["growth"] for it in items]

        summary[cat] = {
            "n": len(items),
            # Loss-side
            "loss_mean_iou":        _mean(it["iou"]            for it in loss_items),
            "loss_mean_precision":  _mean(it["precision"]      for it in loss_items),
            "loss_mean_recall":     _mean(it["recall"]         for it in loss_items),
            "loss_mean_f1":         _mean(it["f1"]             for it in loss_items),
            "loss_mean_area_err":   _mean(it["area_error_pct"] for it in loss_items),
            "loss_fp_rate":         _frac(it["false_positive"] for it in loss_items
                                          if it["truth_pixels"] == 0),
            "loss_mean_false_px":   _mean(it["pred_pixels"]    for it in loss_items
                                          if it["truth_pixels"] == 0),
            # Growth-side
            "growth_mean_iou":       _mean(it["iou"]            for it in growth_items),
            "growth_mean_precision": _mean(it["precision"]      for it in growth_items),
            "growth_mean_recall":    _mean(it["recall"]         for it in growth_items),
            "growth_mean_f1":        _mean(it["f1"]             for it in growth_items),
            "growth_mean_area_err":  _mean(it["area_error_pct"] for it in growth_items),
            "growth_fp_rate":        _frac(it["false_positive"] for it in growth_items
                                           if it["truth_pixels"] == 0),
            "growth_mean_false_px":  _mean(it["pred_pixels"]    for it in growth_items
                                           if it["truth_pixels"] == 0),
        }
    return summary


# ─── REPORT PRINTING ──────────────────────────────────────────────────────────

EMPTY_TRUTH_CATEGORIES = {"identity", "lighting", "homography"}


def _fmt(x, fmt="{:>6.2f}") -> str:
    if x is None:
        return "   —  "
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return "   —  "
    return fmt.format(x)


def _fmt_pct(x) -> str:
    if x is None:
        return "   —   "
    return f"{x * 100:>5.1f}%"


def _fmt_int(x) -> str:
    if x is None:
        return "      —"
    return f"{int(x):>7,}"


def print_summary(report: dict) -> None:
    summary = report["per_category"]
    cfg     = report["config"]

    print()
    print("=" * 78)
    print(f"  EVALUATION SUMMARY — {report['timestamp']}")
    print("=" * 78)
    print(f"  Pipeline   : {'HSV canopy + YOLO cross-validation' if cfg['use_yolo'] else 'HSV canopy only (no YOLO)'}")
    print(f"  Registration: {'enabled (AKAZE + RANSAC)' if cfg.get('use_registration') else 'disabled'}")
    print(f"  Preprocessing: {'enabled (CLAHE + histogram match)' if cfg.get('use_preprocessing') else 'disabled'}")
    print(f"  Veg mask    : {cfg.get('vegetation_source_label', '?')}")
    print(f"  Pairs      : {report['n_pairs']}  "
          f"({report['n_succeeded']} succeeded, {report['n_failed']} failed)")
    print(f"  Min zone   : {cfg['min_zone_px']} px  |  Conf : {cfg['conf']}")
    print(f"  Total time : {report['total_time_s']:.1f}s")
    print()

    # ─ False-positive baseline (truth = empty for all categories below) ─
    fp_cats = [c for c in summary if c in EMPTY_TRUTH_CATEGORIES]
    if fp_cats:
        print("─" * 78)
        print("  FALSE-POSITIVE BASELINE  (truth = empty — any prediction is an error)")
        print("─" * 78)
        print(f"  {'category':<18s}  {'n':>3s}    "
              f"{'loss-FP':>8s}  {'mean-pred-px':>14s}    "
              f"{'growth-FP':>9s}  {'mean-pred-px':>14s}")
        for cat in fp_cats:
            s = summary[cat]
            print(f"  {cat:<18s}  {s['n']:>3d}    "
                  f"{_fmt_pct(s['loss_fp_rate']):>8s}  "
                  f"{_fmt_int(s['loss_mean_false_px']):>14s}    "
                  f"{_fmt_pct(s['growth_fp_rate']):>9s}  "
                  f"{_fmt_int(s['growth_mean_false_px']):>14s}")
        print()

    # ─ Change-detection metrics (truth > 0) ─
    ch_cats = [c for c in summary if c not in EMPTY_TRUTH_CATEGORIES]
    if ch_cats:
        print("─" * 78)
        print("  CHANGE DETECTION         (truth > 0 — IoU is the headline number)")
        print("─" * 78)
        print(f"  {'category':<18s}  {'n':>3s}   {'IoU':>6s}  "
              f"{'prec':>6s}  {'recall':>6s}  {'F1':>6s}  {'area-err':>9s}  "
              f"{'side':>7s}")
        for cat in ch_cats:
            s = summary[cat]
            # Show loss-side row if any loss truth exists in this category
            loss_has_truth = (cat != "growth")
            growth_has_truth = (cat in ("growth", "mixed"))
            if loss_has_truth:
                print(f"  {cat:<18s}  {s['n']:>3d}   "
                      f"{_fmt(s['loss_mean_iou']):>6s}  "
                      f"{_fmt(s['loss_mean_precision']):>6s}  "
                      f"{_fmt(s['loss_mean_recall']):>6s}  "
                      f"{_fmt(s['loss_mean_f1']):>6s}  "
                      f"{_fmt(s['loss_mean_area_err'], '{:>+7.1f}%'):>9s}  "
                      f"{'loss':>7s}")
            if growth_has_truth:
                print(f"  {'':<18s}  {'':>3s}   "
                      f"{_fmt(s['growth_mean_iou']):>6s}  "
                      f"{_fmt(s['growth_mean_precision']):>6s}  "
                      f"{_fmt(s['growth_mean_recall']):>6s}  "
                      f"{_fmt(s['growth_mean_f1']):>6s}  "
                      f"{_fmt(s['growth_mean_area_err'], '{:>+7.1f}%'):>9s}  "
                      f"{'growth':>7s}")
        print()

    # ─ Worst failure modes ─
    print("─" * 78)
    print("  WORST FAILURE MODES")
    print("─" * 78)
    findings = _diagnose_failures(summary)
    if findings:
        for f in findings:
            print(f"  • {f}")
    else:
        print("  (none flagged)")
    print()

    print(f"  Report saved → {report['report_path']}")
    print("=" * 78)


def _diagnose_failures(summary: dict) -> list[str]:
    findings = []
    for cat, s in summary.items():
        if cat in EMPTY_TRUTH_CATEGORIES:
            for side in ("loss", "growth"):
                rate = s.get(f"{side}_fp_rate")
                if rate is not None and rate >= 0.5:
                    findings.append(
                        f"{cat:<18s} pipeline reports {side} on "
                        f"{rate*100:.0f}% of pairs (should be 0%)"
                    )
        else:
            iou = s.get("loss_mean_iou") if cat != "growth" else s.get("growth_mean_iou")
            if iou is not None and iou < 0.30:
                findings.append(
                    f"{cat:<18s} mean IoU {iou:.2f} — significant detection error"
                )
    return findings


# ─── JSON-SAFE CONVERSION ─────────────────────────────────────────────────────

def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if not np.isnan(obj) else None
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, bool):
        return bool(obj)
    return obj


# ─── EVALUATION DRIVER ────────────────────────────────────────────────────────

def evaluate(pairs_dir: Path, out_dir: Path, *,
             use_yolo: bool, model_path: Path,
             device: str, conf: float,
             use_registration: bool,
             use_preprocessing: bool,
             use_exg: bool,
             exg_method: str,
             exg_min_delta: int,
             min_zone_px: int,
             vegetation_source: str,
             seg_model_path: Optional[Path],
             limit: Optional[int]) -> dict:
    pair_dirs = sorted([p for p in pairs_dir.iterdir() if p.is_dir()])
    if not pair_dirs:
        sys.exit(f"No pair directories under {pairs_dir}")
    if limit:
        pair_dirs = pair_dirs[:limit]

    print(f"Found {len(pair_dirs)} pairs under {pairs_dir}")
    model = _yolo_load(model_path, device) if use_yolo else None

    seg_model = None
    if vegetation_source == "seg":
        if seg_model_path is None or not Path(seg_model_path).exists():
            sys.exit(f"vegetation_source='seg' needs --seg-model (got {seg_model_path})")
        print(f"Loading seg model ({device}): {Path(seg_model_path).name}")
        seg_model = load_yolo(seg_model_path)

    veg_label = {
        "seg": "YOLO-seg union (learned)",
        "hsv": "HSV threshold (legacy)",
        "exg": f"{exg_method} + joint Otsu",
    }[vegetation_source]

    per_pair: list[dict] = []
    n_succeeded = 0
    n_failed    = 0
    t_total     = 0.0
    start_all   = time.time()

    for i, pair_dir in enumerate(pair_dirs, 1):
        meta_path = pair_dir / "meta.json"
        if not meta_path.exists():
            print(f"[{i:4d}/{len(pair_dirs)}] {pair_dir.name}  — missing meta.json, skipped")
            n_failed += 1
            continue
        meta = json.loads(meta_path.read_text())

        before_path  = pair_dir / "before.jpg"
        after_path   = pair_dir / "after.jpg"
        loss_truth   = cv2.imread(str(pair_dir / "loss_truth.png"),   cv2.IMREAD_GRAYSCALE)
        growth_truth = cv2.imread(str(pair_dir / "growth_truth.png"), cv2.IMREAD_GRAYSCALE)
        if loss_truth is None or growth_truth is None:
            print(f"[{i:4d}/{len(pair_dirs)}] {pair_dir.name}  — missing truth masks, skipped")
            n_failed += 1
            continue

        t0 = time.time()
        try:
            pred_loss, pred_growth, reg_info, prep_info, veg_info = predict_change(
                before_path, after_path,
                use_yolo=use_yolo, model=model, device=device, conf=conf,
                use_registration=use_registration,
                use_preprocessing=use_preprocessing,
                use_exg=use_exg,
                exg_method=exg_method,
                exg_min_delta=exg_min_delta,
                min_zone_px=min_zone_px,
                vegetation_source=vegetation_source,
                seg_model=seg_model,
            )
        except Exception as e:
            print(f"[{i:4d}/{len(pair_dirs)}] {pair_dir.name}  — pipeline failed: {e}")
            n_failed += 1
            continue
        dt = time.time() - t0
        t_total += dt

        loss_m   = _binary_metrics(pred_loss,   loss_truth)
        growth_m = _binary_metrics(pred_growth, growth_truth)

        entry = {
            "pair_id":       meta["pair_id"],
            "category":      meta["category"],
            "source_h":      meta.get("source_h"),
            "source_w":      meta.get("source_w"),
            "elapsed_s":     dt,
            "registration":  reg_info,
            "preprocessing": prep_info,
            "vegetation":    veg_info,
            "loss":          loss_m,
            "growth":        growth_m,
        }
        per_pair.append(entry)
        n_succeeded += 1

        # Short progress line
        iou_str = (f"IoU={_fmt(loss_m['iou'] if entry['category']!='growth' else growth_m['iou'])}"
                   if (loss_m['truth_pixels'] > 0 or growth_m['truth_pixels'] > 0)
                   else f"FP={'yes' if (loss_m['false_positive'] or growth_m['false_positive']) else 'no '}")
        print(f"[{i:4d}/{len(pair_dirs)}] {entry['pair_id']}  "
              f"{entry['category']:<15s}  {iou_str}  ({dt:.2f}s)")

    per_category = aggregate_by_category(per_pair)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{timestamp}.json"

    report = {
        "timestamp":      timestamp,
        "pairs_dir":      str(pairs_dir.relative_to(PROJECT_ROOT)),
        "n_pairs":        len(pair_dirs),
        "n_succeeded":    n_succeeded,
        "n_failed":       n_failed,
        "total_time_s":   time.time() - start_all,
        "pipeline_time_s": t_total,
        "config": {
            "use_yolo":                use_yolo,
            "use_registration":        use_registration,
            "use_preprocessing":       use_preprocessing,
            "vegetation_source":       vegetation_source,
            "vegetation_source_label": veg_label,
            "exg_method":              exg_method if vegetation_source == "exg" else None,
            "exg_min_delta":           exg_min_delta if vegetation_source == "exg" else None,
            "seg_model":               str(seg_model_path) if vegetation_source == "seg" else None,
            "model_path":              str(model_path) if use_yolo else None,
            "device":                  device if use_yolo else None,
            "conf":                    conf,
            "min_zone_px":             min_zone_px,
            "imgsz":                   INFER_IMGSZ,
        },
        "per_category":   per_category,
        "per_pair":       per_pair,
        "report_path":    str(report_path.relative_to(PROJECT_ROOT)),
    }

    with open(report_path, "w") as f:
        json.dump(_json_safe(report), f, indent=2)

    print_summary(report)
    return report


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pairs", type=Path, default=PAIRS_DEFAULT,
                   help=f"Directory of generated pairs (default: "
                        f"{PAIRS_DEFAULT.relative_to(PROJECT_ROOT)})")
    p.add_argument("--out",   type=Path, default=REPORTS_DEFAULT,
                   help=f"Directory for JSON reports (default: "
                        f"{REPORTS_DEFAULT.relative_to(PROJECT_ROOT)})")
    p.add_argument("--model", type=Path, default=YOLO_MODEL_DEFAULT,
                   help="Path to YOLO checkpoint for cross-validation")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda", "0"],
                   help="YOLO device (default cpu — change to 0 for GPU)")
    p.add_argument("--conf", type=float, default=DEFAULT_CONF,
                   help=f"YOLO confidence threshold (default: {DEFAULT_CONF})")
    p.add_argument("--no-yolo", action="store_true",
                   help="Skip YOLO cross-validation (HSV canopy only)")
    p.add_argument("--no-registration", action="store_true",
                   help="Skip feature-based image registration "
                        "(diff before/after as captured)")
    p.add_argument("--no-preprocessing", action="store_true",
                   help="Skip CLAHE + histogram matching")
    p.add_argument("--veg-source", default="exg",
                   choices=("exg", "hsv", "seg"),
                   help="Vegetation mask source: exg (default), hsv (legacy), "
                        "or seg (learned YOLO-seg union mask)")
    p.add_argument("--seg-model", type=Path,
                   default=PROJECT_ROOT / "models" / "tree_seg.pt",
                   help="Path to the YOLO-seg model (used when --veg-source seg)")
    p.add_argument("--no-exg", action="store_true",
                   help="(legacy) same as --veg-source hsv")
    p.add_argument("--exg-method", default="ExG",
                   choices=("ExG", "ExGR", "CIVE", "VARI"),
                   help="Which vegetation index to use (default: ExG)")
    p.add_argument("--exg-min-delta", type=int, default=20,
                   help="Continuous-diff magnitude gate (0-255). A pixel is "
                        "flagged only if its index changes by >= this. "
                        "0 = plain binary diff (default: 20)")
    p.add_argument("--min-zone-px", type=int, default=CHANGE_MIN_ZONE_PX,
                   help=f"Minimum connected-component size for a change zone "
                        f"(default: {CHANGE_MIN_ZONE_PX}). Higher = fewer "
                        f"false positives but misses small changes.")
    p.add_argument("--limit", type=int, default=None,
                   help="Run on first N pairs only (for quick iteration)")
    args = p.parse_args()

    if not args.pairs.exists():
        sys.exit(f"Pairs directory not found: {args.pairs}")

    # --no-exg is a legacy alias for --veg-source hsv
    veg_source = "hsv" if args.no_exg else args.veg_source

    evaluate(
        pairs_dir=args.pairs,
        out_dir=args.out,
        use_yolo=not args.no_yolo,
        model_path=args.model,
        device=args.device,
        conf=args.conf,
        use_registration=not args.no_registration,
        use_preprocessing=not args.no_preprocessing,
        use_exg=(veg_source == "exg"),
        exg_method=args.exg_method,
        exg_min_delta=args.exg_min_delta,
        min_zone_px=args.min_zone_px,
        vegetation_source=veg_source,
        seg_model_path=args.seg_model,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
