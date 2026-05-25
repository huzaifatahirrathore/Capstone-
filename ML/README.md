# Forest / Vegetation Change Detection

Compares two aerial/drone images of the same area (a **before** and an **after**)
and reports where vegetation was **lost** or **gained**, plus canopy coverage and
optional CO₂/O₂ estimates.

The production engine is **ExG (Excess Green) + Otsu** — pure computer vision.
**No trained model and no GPU are required**; it runs on CPU anywhere.

---

## 1. Setup

```bash
# clone
git clone https://github.com/AsawirShafiq/forest-trees.coco.git
cd forest-trees.coco

# create + activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install dependencies
pip install numpy opencv-python          # minimal — enough for the ExG engine
# OR, for the experimental YOLO/seg options too (heavy, pulls torch):
# pip install -r train/requirements.txt
```

That's it — no model weights to download.

---

## 2. Quick start

The repo ships with sample image pairs (`train/a1.png … b3.png`). Try one:

```bash
python train/compare.py train/a1.png train/b1.png
```

This prints a report and writes an annotated composite to
`train/results/compare_a1_vs_b1_ExG.jpg`.

General form:
```bash
python train/compare.py <BEFORE_IMAGE> <AFTER_IMAGE> [options]
```

---

## 3. What the output means

**Terminal report — per image (BEFORE / AFTER / DELTA):**
- `Canopy %` — fraction of each image that is vegetation
- `Canopy m²` — vegetation area in real-world units
- `CO2 kg/year (seq)` — annual CO₂ sequestration (rate × area, by biome)
- `O2 kg/year` — annual O₂ production (from CO₂ stoichiometry)
- `Est. trees` — rough tree count (canopy m² ÷ avg crown area)
- `Stored carbon kg CO2e` — standing carbon mass in the canopy

**Net change impact** — the headline numbers for deforestation:
- Canopy area gained/lost (m²)
- Annual CO₂ sequestration change (kg/yr)
- Relatable equivalents: avg cars' emissions, people's O₂

**Change zones:**
- `Loss zones` — regions that were vegetation in *before* but not in *after* (with m² + CO₂ lost)
- `Growth zones` — regions that became vegetation in *after*

**Assumptions footer** lists every constant used (scale, biome rate, crown size, etc.) — transparent so users know what's behind the numbers.

> **EST flag:** if `--scale` is not passed, physical figures use an *assumed* scale of 0.05 m/px and are labeled `(EST)`. They're order-of-magnitude only — pass `--scale <m/px>` for accurate values.

**Composite image** (`train/results/…`):
- Left = before with green canopy overlay
- Right = after with **orange = loss**, **cyan = growth**, numbered zones

---

## 4. Options

| Flag | Purpose |
|------|---------|
| `--scale 0.05` | Meters per pixel (e.g. 5 cm/px). **Without it, physical figures default to an assumed 0.05 m/px and are marked `(EST)` — pass this for accurate values.** |
| `--biome tropical` | CO₂ rate constant: `temperate` (default), `tropical`, `boreal`, `mediterranean`. |
| `--min-zone-px 800` | Minimum change-zone size in pixels (default 500). Raise to ignore small change. |
| `--no-save` | Print the report only; don't write the composite image. |

Example with real-world units:
```bash
python train/compare.py before.jpg after.jpg --scale 0.05 --biome temperate
```

---

## 5. Important usage note: use SAME-SEASON pairs

The tool detects *vegetation change*. If `before` and `after` are from
**different seasons** (leaves on vs off), it will report large "loss"/"growth"
that is really just seasonal difference — not tree loss. For meaningful
deforestation results, compare images from the **same time of year**.

---

## 6. Calling it from code (for the web backend)

The engine is a plain Python function — import it directly:

```python
import sys
sys.path.insert(0, "core")
sys.path.insert(0, "train")
from pipeline import compare_pipeline

result = compare_pipeline("before.jpg", "after.jpg")   # ExG, CPU, no model

# result is a ComparisonResult:
result.loss_mask        # uint8 0/255 mask of lost vegetation
result.growth_mask      # uint8 0/255 mask of gained vegetation
result.loss_zones       # list of {cx, cy, area_px, bbox}
result.growth_zones     # same
result.canopy_before    # binary canopy mask (before)
result.canopy_after     # binary canopy mask (after)
result.registration     # dict: was alignment successful, inlier count
result.vegetation       # dict: method, threshold, canopy fractions
result.elapsed_s        # processing time
```

Tunable keyword args: `min_zone_px`, `exg_min_delta`, `use_registration`,
`use_preprocessing`. See `core/pipeline.py` for the full signature.

---

## 7. Notes

- **No model / no GPU needed** for the production (ExG) engine.
- An experimental YOLO-seg mode exists (`--veg-source seg`) but is **not
  recommended** — it does not generalize beyond its training imagery, and the
  weights are not shipped in this repo.
- Pipeline stages (all CPU): image registration (AKAZE+RANSAC) → lighting
  normalization (CLAHE + histogram match) → ExG + Otsu vegetation mask →
  continuous-value change diff.
