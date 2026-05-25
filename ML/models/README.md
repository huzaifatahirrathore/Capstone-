# Models

**The production engine is model-free.** Vegetation detection uses ExG
(Excess Green) + Otsu thresholding in [`core/vegetation.py`](../core/vegetation.py) —
pure computer vision, no neural network, runs on CPU. Nothing in this folder
is required to run the pipeline.

## Why no model ships here

A YOLO-seg model was trained and evaluated, but it **failed to generalize**
to real out-of-distribution imagery (detected ~0–6% canopy on aerial pairs
that were clearly ~40% vegetation). ExG is distribution-agnostic — it finds
green on any imagery — so it was chosen as the production engine. See the
project notes for the full comparison.

## Experimental seg model (optional, local-only)

`tree_seg.pt` (git-ignored, not pushed) can still be used for experiments:

```bash
python train/compare.py before.jpg after.jpg --veg-source seg
```

It only performs well on imagery resembling its training set (close-range
dense canopy). Do not rely on it for arbitrary drone uploads.

## Running the production pipeline (no model needed)

```bash
python train/compare.py before.jpg after.jpg          # ExG, default
```

Just clone, `pip install -r requirements.txt`, and run — no weights, no GPU.
