# Configuration

Copy `.env.example` to `.env` (ignored by Git) and set only what you need; every value has a safe default. Real environment variables always win over the file, which is how `scripts/share.py` and Docker override it. Never commit real provider keys or access tokens.

## AI providers

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN` | empty | Optional provider credentials; never sent to the browser |
| `VLM_PROVIDER` | `Gemini` | Default provider in the interface |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Primary Gemini model |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.6-flash,gemini-3.5-flash-lite,gemini-flash-lite-latest` | Gemini models tried after quota or server errors |
| `OPENAI_MODEL` | `gpt-6-luna` | OpenAI model, called through the Responses API |
| `GROQ_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq vision model |
| `HF_VLM_MODEL`, `HF_PROVIDER` | `google/gemma-3-4b-it`, `auto` | Hugging Face Inference Providers model and routing |
| `VLM_FALLBACK` | `true` | Try another configured provider when the chosen one fails |
| `VLM_FALLBACK_ORDER` | `Gemini,OpenAI,Groq,Hugging Face` | Order of that fallback chain |
| `VLM_SECOND_OPINION` | `true` | Gemini re-checks the spots of single-photo analyses (+1 call) |
| `VLM_TIMEOUT_SECONDS`, `VLM_MAX_RETRIES` | `90`, `2` | Provider timeout and retries for transient errors |
| `VLM_TRUST_ENV_PROXY` | `false` | Honour the system proxy variables (corporate networks) |

Model names change quickly; every one of them is a variable, so a retired model never needs a code change.

## Vision models and data

| Variable | Default | Purpose |
|---|---|---|
| `YOLO_MODEL_PATH`, `YOLO_CONFIDENCE`, `YOLO_IMAGE_SIZE` | `models/acne_like_spot.pt`, `0.10`, `640` | Spot detector weights and settings |
| `FACE_LANDMARKER_PATH` | `models/face_landmarker.task` | MediaPipe model; OpenCV Haar is used when missing |
| `PRODUCT_CATALOG_PATH` | `data/products.json` | Editable product catalog (schema: `data/products.example.json`) |
| `HISTORY_ENABLED`, `HISTORY_DB_PATH` | `true`, `data/history.db` | Profiles, history, journal and shelf storage (SQLite) |

## Limits

| Variable | Default | Purpose |
|---|---|---|
| `MAX_UPLOAD_MB` | `10` | Compressed size per image |
| `MAX_IMAGE_PIXELS` | `40000000` | Decoded pixel count per image (decompression-bomb guard) |
| `MAX_REQUEST_BODY_MB` | `32` | Whole JSON or multipart request, enforced before parsing |
| `ANALYSIS_RATE_LIMIT`, `LABEL_RATE_LIMIT`, `CAPTURE_RATE_LIMIT` | `12`, `30`, `600` | Per-IP hourly limits for analyses, label reading and coach, camera checks |

## Access and sharing

| Variable | Default | Purpose |
|---|---|---|
| `PUBLIC_DEPLOYMENT` | `false` | Enforce production security requirements; the app refuses to start without them |
| `APP_ACCESS_TOKEN` | empty | Shared access token; at least 32 characters in public mode |
| `ALLOW_USER_API_KEYS` | `true` locally, `false` in public mode | Let users type their own provider key |
| `PROFILE_SCOPE` | `shared` locally, `device` in public mode | `device`: each browser sees only the profiles it created |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated browser origins allowed to call the API |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Accepted Host headers; wildcards are rejected in public mode |
| `LOG_LEVEL` | `INFO` | Application log level |

For a public deployment start from `.env.production.example` and follow [deployment.md](deployment.md).
