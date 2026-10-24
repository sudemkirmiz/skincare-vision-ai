# syntax=docker/dockerfile:1.7

# --- 1) React production build ---------------------------------------------
FROM node:22-bookworm-slim AS web

ENV CI=true \
    NPM_CONFIG_UPDATE_NOTIFIER=false

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2) FastAPI + model runtime --------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    XDG_CACHE_HOME=/tmp/cache \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba \
    HOME=/home/appuser

# OpenCV/Torch runtime libraries and an init process for clean signal handling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgl1 libglib2.0-0 libgomp1 libportaudio2 tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt constraints.txt ./
# CPU-only Torch avoids shipping CUDA libraries. MediaPipe is deliberately
# installed without deps so opencv-contrib-python cannot replace YOLO's cv2.
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -c constraints.txt -r requirements.txt \
    && pip install --no-deps mediapipe==1.1.1 \
    && python -c "import cv2, flatbuffers, mediapipe, numpy, torch; print('runtime imports ok')"

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/state /tmp/ultralytics \
    && chown -R appuser:appuser /app/state /tmp/ultralytics

# Copy only runtime artefacts; tests, docs, local data and Git metadata never
# enter the final image.
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser data/products.json data/products.example.json ./data/
COPY --chown=appuser:appuser models/ ./models/
COPY --chown=appuser:appuser assets/ ./assets/
COPY --chown=appuser:appuser LICENSE THIRD_PARTY_NOTICES.md ./
COPY --chown=appuser:appuser licenses/ ./licenses/
COPY --from=web --chown=appuser:appuser /web/dist ./frontend/dist

USER 10001:10001

EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).read()"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "api.server:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
