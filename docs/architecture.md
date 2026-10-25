# Architecture

## Code layout

```text
src/
|-- config.py         settings from the environment (.env as defaults)
|-- api/              FastAPI app: routes, schemas, security middleware, service container, rate limiter
|-- analysis/         pipeline (face crop and quality), multi-view merge, regions, metrics, change maps,
|                     camera guidance and the rule-based local comment
|-- detection/        YOLO spot detector, MediaPipe landmarks, OpenCV Haar fallback
|-- preprocessing/    image I/O and validation, photo-quality checks
|-- recommendation/   routine engine, actives, INCI parsing and verdicts, catalog, shelf and shelf planner
|-- history/          SQLite store with versioned migrations, journal insights, comparisons
|-- output/           JSON writer for the command-line pipeline run
|-- report/           PDF, text, JSON and CSV output
|-- safety/           medical-claim filtering of model output
|-- services/         skincare coach and skin weather (Open-Meteo)
|-- users/            profiles, onboarding rules, profile-versus-photo hints
`-- vlm/              provider clients (Gemini, OpenAI Responses, Groq, Hugging Face), fallback router,
                      circuit breaker and output quality checks
```

HTTP concerns stay in `src/api/server.py`; analysis and business rules are plain, unit-tested modules. `src/api/container.py` owns the long-lived models and services. In production FastAPI serves the compiled React app from `frontend/dist` on the same origin.

The frontend (`frontend/src`) is React 19 with TanStack Query: `pages/` per route, `components/` for cards and panels, `lib/` for the API client, app state, theme and reminders, and `demo/` for the browser-only data layer of the live demo.

## An analysis request

1. The guard checks the access token, the device scope, the request size and the per-IP rate limit.
2. Image type, integrity, compressed size and decoded pixel count are validated.
3. The image is normalized inside an isolated temporary directory and EXIF metadata is stripped.
4. Face and regions are detected; the metrics and the routine are calculated.
5. The provider chain writes the care comment from a face crop and limited context, or the local rule engine writes it.
6. Temporary files are deleted. Only a small preview is kept, and only if the user saves the result.

## Design decisions

- **Measurements first, AI second.** Scores, routine and planner are deterministic and testable; a language model only phrases the comment, reads labels and powers the coach. Without a key the rule engine still explains every number.
- **Resilient providers.** A fallback chain across providers and Gemini models, a circuit breaker per provider and credential, retries with back-off and a response cache keep the comment available under quota limits.
- **Privacy by construction.** Photos never touch the disk, the service worker never caches `/api`, and model requests get only the face crop, the preferred name and form of address.
- **Device-scoped sharing.** A random browser key, stored server-side only as a SHA-256 hash, isolates friends on one shared link without accounts.
- **One codebase for the demo.** The live demo is the same React build with the API answered in the browser from recorded responses (`--mode demo`), so it cannot drift from the real app.

## Analysis methodology

| Sub-score | Measurement | Weight |
|---|---|---:|
| Spot density | YOLO, colour candidates, optional Gemini second opinion | 35% |
| Redness balance | CIELAB a* distribution and regional differences | 25% |
| Tone evenness | Brightness variation after illumination normalization | 15% |
| Texture smoothness | Fine-scale luminance energy | 15% |
| Shine control | Specular-highlight area | 10% |

White balance is corrected from the sclera when the eyes are visible. Calibration thresholds live in `src/analysis/skin_metrics.py`. Lighting, camera, pose and image quality affect every result; the scores are not clinical measurements.

## API overview

| Area | Representative endpoints |
|---|---|
| Health and configuration | `GET /api/health`, `GET /api/status`, `GET /api/options` |
| Profiles | `GET/POST /api/profiles`, `GET/PUT/DELETE /api/profiles/{id}` |
| Analysis | `POST /api/analyses`, routine, products, report and save |
| History and comparison | history, thumbnails, comparisons, change maps and exports |
| Journal and events | daily journal and routine events |
| Product shelf | shelf CRUD with checks and the generated plan |
| Product review | ingredient check and photographed-label reading |
| Coach and weather | suggestions, chat, location search and weather context |
| Camera guidance | `POST /api/capture/check` |

38 API endpoints in total. Interactive OpenAPI documentation is served at `/docs` outside public mode.
