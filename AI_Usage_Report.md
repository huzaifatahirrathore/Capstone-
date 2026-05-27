## 1. UI / UX Design — Google Stitch & Gemini

| What               | Detail                                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Tool**           | Google Stitch (AI UI prototyping) + Gemini (ideation)                                                                 |
| **Purpose**        | Generated the initial wireframe and visual concept for the web dashboard                                              |
| **Scope**          | Login page, Plantation Projects page, Satellite Analysis page, overall dark-green colour palette, card/widget layouts |
| **Relevant files** | `frontend/src/pages/`, `frontend/src/components/`                                                                     |

The AI-generated prototype served as the design reference that the team then coded in **React + Tailwind CSS**. The component structure (TopNav, MetricWidget, CanopyViewport, FileDropzone, ScanTimeline, etc.) follows the Stitch-generated layout directly.

---

## 2. Tree Detection Model — YOLOv8 / YOLO26 (Ultralytics)

| What                  | Detail                                                                              |
| --------------------- | ----------------------------------------------------------------------------------- |
| **Model family**      | Ultralytics YOLO (YOLOv8 / YOLO26 variants)                                         |
| **Task**              | Object detection — localise individual trees in aerial/drone imagery                |
| **Architecture used** | `yolo26m.pt` (medium, detection) · `yolo26m-seg.pt` (medium, instance segmentation) |

### 2a. Detection model training (`ML/train/main.py`)

- Pre-trained YOLO26-medium weights used as the starting point (transfer learning).
- Fine-tuned for 200 epochs on a custom aerial-tree dataset at `imgsz=960`, `batch=2`.
- Augmentation applied during training: mosaic (1.0), mixup (0.15), random scale ±50 %, horizontal/vertical flip, HSV colour jitter (hue, saturation, brightness).
- Early stopping (`patience=30`).
- Trained on an **RTX 3060 Laptop GPU** (6 GB VRAM).
- Final weights saved to `runs/detect/runs/tree_detect/yolo26m_trees-8/weights/best.pt`.

### 2b. Segmentation model training (`ML/train/train_seg.py`)

- Separate YOLO-seg model trained to produce **per-tree instance masks** (pixel-level polygons).
- 100 epochs, `imgsz=640` (seg requires more VRAM than detection — 960 OOM'd on the 6 GB GPU).
- Augmentations: mosaic, copy-paste (0.3), scale, flip.
- Cosine LR schedule (`cos_lr=True`).

### 2c. Inference / deployment (`ML/train/detect.py`, `backend/python-service/app.py`)

- At runtime, the detection model runs on uploaded images via the `/detect` API endpoint.
- Supports **tiled inference** for very large images (> 1920 px), with cross-tile NMS to merge duplicate boxes.
- Confidence threshold: 0.25 (default); IoU NMS: 0.6.

---

## 3. Dataset — Roboflow + Custom Annotation

| What               | Detail                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------- |
| **Source**         | Roboflow Universe — "forest trees" dataset                                             |
| **Size**           | 3,157 aerial/satellite images of trees                                                 |
| **Format**         | COCO annotation format → converted to YOLO format                                      |
| **Exported**       | March 2, 2026 via roboflow.com                                                         |
| **Relevant files** | `ML/train/dataset/dataset.yaml`, `ML/README.roboflow.txt`, `ML/train/coco_to_yolov.py` |

Roboflow's AI-assisted annotation platform was used to manage, inspect and export the labelled dataset. The dataset was then split into train / val / test splits defined in `dataset.yaml`.

---

## 4. SAM (Segment Anything Model) — Meta AI (`ML/train/refine_masks_with_sam.py`)

| What        | Detail                                                                           |
| ----------- | -------------------------------------------------------------------------------- |
| **Model**   | SAM ViT-B (`sam_vit_b_01ec64.pth`) — Meta AI                                     |
| **Purpose** | Refine coarse YOLO bounding-box detections into precise pixel-level canopy masks |

### How it was used

1. The trained YOLO detection model runs on every training image to produce bounding boxes.
2. Each bounding box is passed as a **prompt** to SAM's `SamPredictor`.
3. SAM returns a precise binary canopy mask (not just the rectangle).
4. The mask is converted to a normalised polygon and saved as a YOLO-seg label file.

This pipeline (`refine_dataset()`) was run once as a data-preparation step (~1–2 hours on RTX 3060) to produce the `dataset/labels_seg/` directory used for segmentation training.

---

## 5. Computer-Vision AI Pipeline — Vegetation Change Detection

This is the **core intelligence layer** of the system. It takes a _before_ and _after_ aerial image and outputs exactly where vegetation was lost or gained. All modules are in `ML/core/` and `ML/train/`.

### 5a. Image Registration — AKAZE + RANSAC (`ML/core/registration.py`)

| Algorithm                                           | Role                                                                                                           |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **AKAZE** (Accelerated-KAZE)                        | Keypoint detector & binary descriptor extractor; robust to scale/rotation differences between two drone passes |
| **Brute-force Hamming matcher + Lowe's ratio test** | Filters good feature correspondences                                                                           |
| **RANSAC homography** (`cv2.findHomography`)        | Estimates a perspective transform that maps the _after_ image onto the _before_ coordinate frame               |

Without this step, even a small camera-angle difference between passes would look like vegetation change. The module validates the homography (inlier count ≥ 15, inlier ratio ≥ 30 %, determinant check) and falls back to identity alignment if registration fails.

### 5b. Lighting Normalisation — CLAHE + Histogram Matching (`ML/core/preprocessing.py`)

| Algorithm                                                                                        | Role                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **CLAHE** (Contrast-Limited Adaptive Histogram Equalisation) on the L channel (LAB colour space) | Normalises within-image local contrast (shadows under one tree vs another)                                                                             |
| **Masked histogram matching**                                                                    | Matches the colour distribution of _after_ onto _before_, computed from **non-vegetation pixels only** — so real canopy changes are not "matched away" |

This stage cuts false-positive rates on lighting-variant pairs from ~100 % to ~8 %.

### 5c. Vegetation Index + Adaptive Thresholding (`ML/core/vegetation.py`)

Instead of a fixed HSV colour range, the system uses **continuous vegetation indices** combined with **Otsu's adaptive threshold**:

| Index                                           | Formula                                       | Reference                 |
| ----------------------------------------------- | --------------------------------------------- | ------------------------- |
| **ExG** (Excess Green) — _production default_   | `2G − R − B`                                  | Woebbecke 1995            |
| **ExGR** (Excess Green minus Red)               | `3G − 2.4R − B`                               | Meyer & Camargo Neto 2008 |
| **CIVE** (Color Index of Vegetation Extraction) | `0.441R − 0.811G + 0.385B + 18.787` (negated) | —                         |
| **VARI** (Visible Atmospheric Resistance Index) | `(G−R)/(G+R−B)`                               | —                         |

A **joint Otsu threshold** is computed from the combined pixel distribution of both images simultaneously — this prevents per-image threshold drift that causes phantom change at every canopy boundary.

### 5d. Continuous-Value Change Detection (`ML/core/vegetation.py` → `continuous_change_masks`)

A pixel is flagged as **loss** only when:

- It was above the vegetation threshold in _before_, and
- It fell below the threshold in _after_, **and**
- Its ExG index value changed by at least `min_delta = 20` (on a 0–255 scale)

The magnitude gate rejects edge-flicker from sub-pixel registration or JPEG noise while keeping genuine large changes.

### 5e. YOLO Cross-Validation (optional, `ML/train/canopy.py` → `cross_validate`)

When enabled, YOLO bounding boxes are used as a **second opinion** on the colour-based canopy mask:

- Vegetation regions confirmed by YOLO → kept as high-confidence detections
- Large canopy regions without YOLO → kept (forest interior)
- Small canopy regions without YOLO → dropped as noise
- YOLO boxes with < 20 % canopy fill → dropped as false positives

### 5f. Full Pipeline (`ML/core/pipeline.py`)

`compare_pipeline()` is the single entry point that chains all the above stages:

```
Registration (AKAZE+RANSAC)
  → Preprocessing (CLAHE + histogram match)
    → Vegetation mask (ExG + joint Otsu + continuous diff)
      → Optional YOLO cross-validation
        → Change-zone diff + connected-component filtering
          → ComparisonResult (loss_mask, growth_mask, loss_zones, growth_zones, metrics)
```

Environmental estimates (CO₂ sequestration, O₂ production, carbon stock, tree count) are computed from the canopy pixel area using biome-specific constants.

---

## 6. Backend AI Invocation (`backend/server.js`, `backend/python-service/app.py`)

The Node.js backend bridges the React frontend to the Python AI pipeline:

- **`POST /detect`** — forwards an uploaded image to the Flask microservice which runs the YOLO detection model.
- **`POST /compare`** — spawns `ML/train/compare.py` as a child process, captures its JSON output (`--json-output` flag), and returns the annotated composite image (base64) plus structured metrics to the frontend.

---

## 7. Frontend AI Output Display (`frontend/src/pages/SatelliteAnalysisPage.jsx`)

The Satellite Analysis page consumes and presents the AI pipeline output:

- **CanopyViewport** — renders the annotated before/after composite image produced by the CV pipeline (green = canopy, orange = loss zones, cyan = growth zones).
- **Conclusion panel** — auto-generates plain-English bullet points from the raw metrics (canopy %, CO₂ change, O₂ change, zone count, vegetation method used).
- **MetricWidget** — displays canopy change (m²) and CO₂ sequestration change (kg/yr).
- **AI Confidence Score badge** — displays model performance metrics (Precision 97.2 %, Recall 94.8 %, F1 0.96).
- **Raw API Response** — shows the JSON payload from the backend for transparency.

---

## 8. Summary Table

| Area                    | AI Technology Used                           | Where in Project                          |
| ----------------------- | -------------------------------------------- | ----------------------------------------- |
| UI Design               | Google Stitch, Gemini                        | All frontend pages                        |
| Tree Detection          | YOLOv8 / YOLO26 (Ultralytics) — fine-tuned   | `ML/train/main.py`, `detect.py`, `app.py` |
| Tree Segmentation       | YOLO-seg (Ultralytics)                       | `ML/train/train_seg.py`                   |
| Mask Refinement         | SAM ViT-B (Meta AI)                          | `ML/train/refine_masks_with_sam.py`       |
| Dataset Management      | Roboflow (AI-assisted labelling platform)    | `ML/train/dataset/`                       |
| Image Registration      | AKAZE + RANSAC (OpenCV)                      | `ML/core/registration.py`                 |
| Lighting Normalisation  | CLAHE + Histogram Matching (OpenCV)          | `ML/core/preprocessing.py`                |
| Vegetation Masking      | ExG / ExGR / CIVE / VARI + Otsu (OpenCV)     | `ML/core/vegetation.py`                   |
| Change Detection        | Continuous-value diff + connected components | `ML/core/pipeline.py`                     |
| Canopy Cross-validation | YOLO bbox cross-check                        | `ML/train/canopy.py`                      |
| Environmental Estimates | Algorithmic (CO₂ / O₂ stoichiometry)         | `ML/train/compare.py`                     |

---

_Document prepared: May 27, 2026_
