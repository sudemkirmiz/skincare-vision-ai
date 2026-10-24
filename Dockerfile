# --- 1) Build the React frontend -------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2) Python API that also serves the built frontend ---------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics

# OpenCV runtime libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# CPU-only torch keeps the image ~1.5 GB smaller than the default CUDA build.
# mediapipe is installed without deps: its opencv-contrib-python would overwrite the cv2 used by YOLO.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt \
    && pip install --no-deps mediapipe==1.1.1

COPY . .
COPY --from=web /web/dist ./frontend/dist

RUN useradd --create-home --uid 1000 appuser && mkdir -p data outputs && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "api.server:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
