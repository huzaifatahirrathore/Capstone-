# EcoLedger

An enterprise platform for plantation project tracking and AI-powered satellite canopy analysis. Organizations can register plantation zones, monitor tree coverage over time, and verify carbon sequestration metrics using computer-vision change detection.

---

## Architecture

```
┌─────────────────────┐     REST/JSON      ┌────────────────────────┐
│   React Frontend    │ ──────────────────▶ │   Node.js Backend      │
│   (Vite + Zustand)  │                    │   (Express + PostgreSQL)│
└─────────────────────┘                    └────────────┬───────────┘
                                                        │ spawns
                                                        ▼
                                            ┌────────────────────────┐
                                            │   Python ML Service    │
                                            │   (ExG + Otsu, CPU)    │
                                            └────────────────────────┘
```

---

## Tech Stack

| Layer    | Technology |
|----------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS v4, Zustand v5, React Router v7, Axios |
| Backend  | Node.js, Express v5, PostgreSQL (`pg`), JWT (`jsonwebtoken`), bcryptjs, multer |
| ML       | Python, OpenCV, NumPy — ExG+Otsu vegetation masking, AKAZE+RANSAC image registration |

---

## Features

### Plantation Projects Dashboard
- Interactive France SVG map with teal-highlighted plantation zones
- Sidebar project list with search and filters (region, sponsor, status)
- Project detail panel with hectares, goal achievement, and blockchain verification badge

### New Project Wizard (3 steps)
1. **Basic Info** — name, region, sponsor, status, hectares, goal %, thumbnail URL, blockchain verified toggle
2. **GPS Boundary** — enter lat/lng coordinate pairs; live SVG map preview of the polygon
3. **Blockchain Registration** — on-chain project record signing (registry integration point)

### AI Satellite Analysis
- Upload before/after satellite images via drag-and-drop
- Animated 5-stage scan timeline while analysis runs
- Output: canopy viewport with glow-overlay change zones, NDVI delta, carbon sequestration estimate, AI confidence score ring
- Powered by the Python ML pipeline (ExG+Otsu, no GPU required)

### Auth
- JWT-based login with `sessionStorage` token storage
- Zustand `persist` store keeps session across page reloads
- Protected routes — all pages behind `/dashboard` require authentication

---

## Project Structure

```
Capstone-/
├── frontend/               # React SPA
│   └── src/
│       ├── api/            # Axios call wrappers (Auth, Projects, Analysis)
│       ├── common/         # Generic primitives (Icons, FilterSelect, ProgressBar)
│       ├── components/     # Feature components (TopNav, ProjectCard, BoundaryMapCard, …)
│       ├── constants/      # Urls.js, Utils.js
│       ├── data/           # Mock seed data (plantationProjects.js)
│       ├── pages/          # LoginPage, PlantationProjectsPage, NewProjectWizardPage, SatelliteAnalysisPage
│       ├── routes/         # AppRoutes.jsx + ProtectedRoute
│       └── store/          # Zustand stores (authStore, projectsStore, analysisStore)
│
├── backend/                # Express REST API
│   ├── server.js           # All routes + auth middleware
│   ├── db.js               # PostgreSQL pool
│   ├── migrations/         # SQL migration files
│   └── python-service/     # Bridge to ML pipeline
│
└── ML/                     # Python change-detection engine
    ├── core/               # pipeline.py, vegetation.py, registration.py, preprocessing.py
    └── train/              # compare.py CLI + sample images + results/
```

---

## Getting Started

### Prerequisites
- Node.js ≥ 18
- PostgreSQL
- Python ≥ 3.9 with `numpy` and `opencv-python`

### 1. Backend

```bash
cd backend
npm install
# Create a .env file:
#   DATABASE_URL=postgres://user:pass@localhost:5432/ecoledger
#   JWT_SECRET=your_secret_key
node server.js        # runs on port 3000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev           # runs on http://localhost:5173
```

### 3. ML (optional — backend spawns this automatically)

```bash
cd ML
python -m venv .venv
source .venv/bin/activate
pip install numpy opencv-python
# Test directly:
python train/compare.py train/a1.png train/b1.png
```

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/signup` | — | Register a new user |
| POST | `/login` | — | Returns JWT token |
| GET | `/users` | ✓ | List all users |
| GET/PUT/DELETE | `/users/:id` | ✓ | User CRUD |
| GET | `/projects` | ✓ | List plantation projects |
| POST | `/projects` | ✓ | Create a new project |
| GET/PUT/DELETE | `/projects/:id` | ✓ | Project CRUD |
| POST | `/detect` | — | Run vegetation detection on a single image |
| POST | `/compare` | — | Run before/after canopy change analysis |
| GET | `/health` | — | Backend health check |

---

## ML Pipeline

The analysis engine (`ML/core/pipeline.py`) requires no trained model and no GPU:

1. **Image registration** — AKAZE keypoint matching + RANSAC homography to align the two images
2. **Preprocessing** — CLAHE contrast enhancement + histogram matching for lighting normalisation
3. **Vegetation masking** — Excess Green index (ExG) + Otsu threshold to separate canopy from soil
4. **Change detection** — pixel-level diff of before/after masks to identify loss and growth zones

Output includes canopy percentage, area (m²), estimated CO₂ sequestration (kg/yr), O₂ production, estimated tree count, and annotated composite image.

> For accurate physical measurements pass `--scale <m/px>` matching your imagery resolution. Without it, figures are estimated at 0.05 m/px and marked `(EST)`.

---

## Design System

| Token | Value | Usage |
|-------|-------|-------|
| Terracotta | `#A3431F` | Top nav, primary CTA |
| Teal | `#008080` | Active states, progress, buttons |
| Cyan | `#00E6E6` | AI/data highlights, glow effects |
| Sand | `#EFE8DC` | Page backgrounds (light theme) |
| Charcoal | `#2C2D30` | Satellite analysis page background |
