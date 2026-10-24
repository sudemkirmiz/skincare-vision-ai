# SkinCare Vision AI

**Kişisel cilt bakım asistanı** — a web app that analyses a face photo for care-oriented skin appearance, builds a personal routine and helps the user track progress over time.

FastAPI · React 19 · TypeScript · Tailwind CSS v4 · YOLO · MediaPipe · OpenCV · Gemini / Groq / Hugging Face

> **Not a medical device.** The app gives a cosmetic, visual pre-assessment only. It does not diagnose, name diseases, recommend prescription products or replace a dermatologist.

---

## Features

**Analysis**
- 1–3 photos (front, left, right) or **guided camera capture** with live hints for distance, centring, head pose, light and sharpness; the photo is taken automatically when everything is right.
- MediaPipe 478-point face mesh → forehead, nose, cheeks and chin regions (eyes, brows and lips excluded); OpenCV Haar fallback.
- Custom YOLO detector (`acne_like_spot`) plus colour-based spot candidates and an optional Gemini second opinion that confirms or adds spots.
- Sclera-based white balance, then five model-free sub-scores (spot density, redness, tone evenness, texture, shine) combined into a 0–100 **Skin Score**.
- A care-oriented AI comment that addresses the user by name in the chosen *siz/sen* form.

**Routine and products**
- Rule-based morning/evening routine with reasons, contraindication checks (pregnancy, age, sensitivity, allergies) and a weekly evening plan that keeps conflicting actives apart.
- **Ingredient checker**: paste an INCI list or photograph the label; the verdict is *Suitable / Use with care / Not recommended* for the current profile.
- **Product shelf**: per-product verdicts, evening conflicts, duplicate actives, missing steps and period-after-opening reminders.
- Product suggestions from an editable catalog with store-search fallback.

**Tracking**
- History with trends, routine events and **aligned before/after**: a drag slider and redness / dark-mark change maps that cancel lighting and shading differences.
- **Daily journal**: routine adherence, skin feel, triggers and symptoms, a 4-week calendar and personal insights (e.g. "after short-sleep days your skin felt 1.6 points worse").
- Two-page PDF report, JSON/CSV export and one-click erasure.

**Helpers**
- **Skin weather**: today's UV, temperature and humidity (Open-Meteo) turned into profile-aware tips.
- **Skin coach** chat grounded in the profile, routine, shelf, journal and weather.

## Architecture

```text
frontend/ (React + Vite)  ──/api──▶  src/api/server.py (FastAPI)
                                       ├─ analysis/      face mesh, regions, metrics, white balance, multi-view,
                                       │                 second opinion, capture guide, change map
                                       ├─ detection/     YOLO + MediaPipe + Haar
                                       ├─ recommendation/ routine engine, ingredients, INCI checker, catalog, shelf
                                       ├─ history/       SQLite store, comparison, journal insights
                                       ├─ vlm_engine.py  Gemini / Groq / Hugging Face clients
                                       ├─ vlm_router.py  provider fallback, circuit breaker, cache
                                       ├─ coach.py       skin coach        weather.py  Open-Meteo + tips
                                       └─ report/        PDF / text / JSON reports
```

In production FastAPI also serves the built frontend (`frontend/dist`), so the whole app runs on one port.

## Quick start

Requirements: Python 3.10+ (tested on 3.12 and 3.13), Node.js 20+ and at least one VLM API key for AI comments (the rest works without).

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
pip install --no-deps mediapipe==1.1.1   # without opencv-contrib, which would replace YOLO's cv2
Copy-Item .env.example .env              # then add your keys

# Frontend
cd frontend
npm install
npm run build
cd ..

# Run
.venv\Scripts\python -m uvicorn api.server:app --app-dir src --port 8000
```

Open http://localhost:8000. API docs are at `/docs`.

**Development with hot reload** (two terminals):

```powershell
.venv\Scripts\python -m uvicorn api.server:app --app-dir src --port 8000 --reload
cd frontend; npm run dev    # http://localhost:5173, proxies /api to port 8000
```

The model files `models/acne_like_spot.pt` and `models/face_landmarker.task` (Apache 2.0) are part of the repository. If the face landmarker is missing:

```powershell
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
```

## Configuration

All settings live in `.env` (see `.env.example`); everything except the keys has a safe default.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN` | – | Provider keys (only the ones you use) |
| `VLM_PROVIDER` | `Gemini` | Default provider in the UI |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODELS` | `gemini-3.5-flash` / `gemini-flash-lite-latest,gemini-2.5-flash` | Gemini models, tried in order on quota or server errors |
| `GROQ_MODEL`, `HF_VLM_MODEL`, `HF_PROVIDER` | see `.env.example` | Other provider models |
| `VLM_FALLBACK` / `VLM_FALLBACK_ORDER` | `true` / `Gemini,Groq,Hugging Face` | Try other providers that have a key |
| `VLM_SECOND_OPINION` | `true` | Gemini spot check (+1 call per single-photo analysis) |
| `VLM_TIMEOUT_SECONDS` / `VLM_MAX_RETRIES` / `VLM_TRUST_ENV_PROXY` | `90` / `2` / `false` | Network behaviour |
| `YOLO_MODEL_PATH` / `YOLO_CONFIDENCE` | `models/acne_like_spot.pt` / `0.10` | Detector |
| `FACE_LANDMARKER_PATH` | `models/face_landmarker.task` | Face mesh model |
| `HISTORY_ENABLED` / `HISTORY_DB_PATH` | `true` / `data/history.db` | Profiles, history, journal and shelf |
| `PRODUCT_CATALOG_PATH` | `data/products.json` | Editable product catalog |
| `MAX_UPLOAD_MB` / `MAX_IMAGE_PIXELS` | `10` / `40000000` | Upload limits |
| `ALLOW_USER_API_KEYS` | `true` | Let users type a personal key in the AI settings |
| `CORS_ORIGINS` | `http://localhost:5173` | Extra origins allowed to call the API |
| `LOG_LEVEL` | `INFO` | Logging |

## Privacy and safety

- Uploaded photos are processed in a private temp directory and deleted right after analysis; EXIF data is stripped. Only results and, if the user agrees, a 320 px face thumbnail are saved.
- Server API keys never reach the browser; the health endpoint only reports whether a key exists. A personal key typed in the UI stays in memory for that tab.
- AI providers receive the face crop, detection results, the routine and the display name with the address form — **never** the surname, age, gender, pregnancy or allergy answers. For the coach these answers only become a neutral "do not suggest" ingredient list.
- Every AI response passes a safety filter that removes diagnoses, disease names, prescription drugs and treatment claims.
- Camera preview frames are checked in memory and never stored. The weather service only sends coordinates rounded to ~10 km; the location stays in the browser.
- All data of a profile (history, thumbnails, journal, shelf) can be exported or deleted at any time.
- For a public deployment set `ALLOW_USER_API_KEYS=false` and `HISTORY_ENABLED=false` (there are no user accounts yet) and put the app behind HTTPS.

## How it works

<details>
<summary><b>Skin Score</b></summary>

All five sub-scores come from classical image processing on a scale-normalised face crop, after sclera-based white balance:

| Sub-score | Measured from | Weight |
|---|---|---|
| Spot density | YOLO findings + colour spot candidates (+ Gemini second opinion) | 35% |
| Redness balance | CIELAB a* (90th percentile + locally redder area) | 25% |
| Tone evenness | lightness variation after removing illumination | 15% |
| Texture smoothness | fine-scale lightness energy | 15% |
| Shine control | specular highlight coverage | 10% |

Thresholds live in `CALIBRATION` in `src/analysis/skin_metrics.py`. They are visual indices that depend on lighting and camera, not clinical measurements. With several photos each region is measured from the view where it is best visible.
</details>

<details>
<summary><b>Routine engine and ingredient checker</b></summary>

Each concern gets a 0–1 need from its sub-score, boosted by the user's goals and skin type. Actives come from a curated cosmetic knowledge base (`src/recommendation/ingredients.py`) with targets, timing, frequency, cautions and conflicts. Pregnancy, under-18s, very sensitive skin, salicylate sensitivity and dry skin exclude unsuitable actives, and every exclusion is shown with its reason. Conflicting actives get separate evenings in the weekly plan.

The INCI checker detects actives, fragrance allergens, essential oils, drying alcohols near the top of the list and potentially pore-clogging ingredients. Labels carry no concentrations, so only ingredient order is used as a hint.
</details>

<details>
<summary><b>Guided capture and change maps</b></summary>

About twice a second a 360 px preview frame goes to `POST /api/capture/check`, which runs the face landmarker and returns the first thing to fix. Three good frames in a row trigger the full-resolution photo.

The change map aligns the later thumbnail to the earlier one with a similarity transform on rigid landmarks. Both photos are band-pass filtered inside the shared skin area (a fine blur against noise minus a wide background that skips spots), so lighting direction, shading and colour cast cancel out and only spot-scale change remains. Notes warn about poor alignment or different head angles.
</details>

<details>
<summary><b>Journal insights</b></summary>

`src/history/insights.py` compares the user's own days: skin feel and symptom rates on the day after days with vs. without a trigger (the period is compared same-day), irritation after evening actives, the effect of the evening routine and adherence between saved analyses. Nothing is shown before 7 logged days, each finding needs at least 3 days on both sides, and findings are worded as associations, not causes.
</details>

<details>
<summary><b>AI reliability</b></summary>

Provider errors are classified (auth, credits, quota, network, server, config, blocked, bad output) and shown with a specific cause. Failed providers or Gemini models are benched for a cooldown (circuit breaker), other providers with a key are tried in order, identical requests reuse a one-hour cache, and comments are validated with Pydantic and checked against the analysis (severity wording, most affected region, excluded ingredients, address form).
</details>

## Testing

```powershell
pip install -r requirements-dev.txt
ruff check .
pytest

cd frontend
npm run lint
npm run typecheck
npm test
```

Tests never touch the network: a fixture blocks real HTTP and every provider call is mocked. `frontend/scripts/screens.mjs` drives the app in headless Chromium for visual review; run it against a throwaway backend (`HISTORY_DB_PATH=outputs/e2e.db`). `scripts/evaluate_samples.py` runs a regression over local photos in `samples/` (git-ignored; add `--vlm Gemini` to include AI comments).

## Docker

```powershell
docker build -t skincare-vision-ai .
docker run --rm -p 8000:8000 --env-file .env -v skincare-data:/app/data skincare-vision-ai
```

The first stage builds the frontend with Node; the final image uses CPU-only PyTorch, runs as a non-root user and has a health check at `/api/health`. The volume keeps the database between restarts.

## Project structure

```text
src/
  api/              FastAPI app, request schemas, shared service container
  analysis/         service, regions, skin metrics, colour balance, multi-view, second opinion,
                    capture guide, change map
  detection/        YOLO spot detector, MediaPipe face mesh, Haar fallback
  recommendation/   profile, ingredients, routine engine, INCI checker, catalog, shelf
  history/          SQLite store (schema migrations), comparison, journal insights
  report/           PDF (ReportLab + Poppins), text and JSON reports, file names
  users/            user profile, onboarding rules, skin-type quiz
  safety/           response safety filter and disclaimer
  vlm_engine.py, vlm_router.py, vlm_quality.py, health.py, coach.py, weather.py, config.py
frontend/src/
  pages/            Onboarding, Analyze, Products (shelf + checker), Tracking, History
  components/       UI kit, results, routine, camera, change map, shelf, weather, coach
  icons/            custom duotone skincare icon set
tests/              pytest suite (offline)
data/               products.json (catalog, starts empty) and products.example.json
models/             YOLO weights and MediaPipe face landmarker
docs/               dataset and training notes for the YOLO model
```

## YOLO model

The detector has one class, `acne_like_spot`. It is a first version (mAP50 ≈ 0.37), which is why colour analysis and the optional Gemini second opinion complement it. Dataset and training notes are in `docs/`. Retraining with more close-up photos, varied lighting and skin tones, and negative examples (freckles, pores, moles, shadows) is the most valuable next improvement.

## Roadmap

- User accounts, so history can be enabled on a public deployment
- A retrained, stronger spot detector
- A curated product catalog
