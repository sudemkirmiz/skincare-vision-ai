from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(env_path: Path = PROJECT_ROOT / ".env") -> None:
    """Minimal .env loader; real environment variables always win."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key and key not in os.environ:
            os.environ[key] = value


def _env_str(key: str, default: str) -> str:
    value = os.getenv(key, "").strip()
    return value or default


def _env_path(key: str, default: str) -> Path:
    path = Path(_env_str(key, default))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    yolo_model_path: Path
    face_landmarker_path: Path
    product_catalog_path: Path
    history_db_path: Path
    history_enabled: bool
    yolo_confidence: float
    yolo_image_size: int
    gemini_model: str
    gemini_fallback_models: tuple[str, ...]
    groq_model: str
    hf_model: str
    hf_provider: str
    vlm_timeout_seconds: float
    vlm_max_retries: int
    vlm_trust_env_proxy: bool
    vlm_fallback: bool
    vlm_second_opinion: bool
    vlm_fallback_order: tuple[str, ...]
    max_upload_mb: int
    max_image_pixels: int
    max_request_body_mb: int
    allow_user_api_keys: bool
    public_deployment: bool
    app_access_token: str
    analysis_rate_limit: int
    label_rate_limit: int
    capture_rate_limit: int
    log_level: str


def get_settings() -> Settings:
    return Settings(
        yolo_model_path=_env_path("YOLO_MODEL_PATH", "models/acne_like_spot.pt"),
        face_landmarker_path=_env_path("FACE_LANDMARKER_PATH", "models/face_landmarker.task"),
        product_catalog_path=_env_path("PRODUCT_CATALOG_PATH", "data/products.json"),
        history_db_path=_env_path("HISTORY_DB_PATH", "data/history.db"),
        # Public multi-user deployments need accounts first; keep history off there.
        history_enabled=_env_bool("HISTORY_ENABLED", True),
        yolo_confidence=_env_float("YOLO_CONFIDENCE", 0.10),
        yolo_image_size=_env_int("YOLO_IMAGE_SIZE", 640),
        gemini_model=_env_str("GEMINI_MODEL", "gemini-3.5-flash"),
        gemini_fallback_models=tuple(
            m.strip() for m in _env_str("GEMINI_FALLBACK_MODELS", "gemini-flash-lite-latest,gemini-2.5-flash").split(",") if m.strip()
        ),
        groq_model=_env_str("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        hf_model=_env_str("HF_VLM_MODEL", "google/gemma-3-4b-it"),
        hf_provider=_env_str("HF_PROVIDER", "auto"),
        vlm_timeout_seconds=_env_float("VLM_TIMEOUT_SECONDS", 90.0),
        vlm_max_retries=max(0, _env_int("VLM_MAX_RETRIES", 2)),
        # Proxy env vars were previously wiped globally; now opt-in via this flag.
        vlm_trust_env_proxy=_env_bool("VLM_TRUST_ENV_PROXY", False),
        # If the chosen provider fails, try the others (that have a key) in this order.
        vlm_fallback=_env_bool("VLM_FALLBACK", True),
        # Gemini re-checks the spots (+1 call per single-photo analysis).
        vlm_second_opinion=_env_bool("VLM_SECOND_OPINION", True),
        vlm_fallback_order=tuple(
            name.strip() for name in _env_str("VLM_FALLBACK_ORDER", "Gemini,Groq,Hugging Face").split(",") if name.strip()
        ),
        max_upload_mb=max(1, _env_int("MAX_UPLOAD_MB", 10)),
        max_image_pixels=max(1, _env_int("MAX_IMAGE_PIXELS", 40_000_000)),
        max_request_body_mb=max(2, _env_int("MAX_REQUEST_BODY_MB", 32)),
        # In a public deployment, visitors should not be able to swap API keys.
        allow_user_api_keys=_env_bool("ALLOW_USER_API_KEYS", True),
        # Public mode is fail-closed: create_app refuses to start without an access token.
        public_deployment=_env_bool("PUBLIC_DEPLOYMENT", False),
        app_access_token=os.getenv("APP_ACCESS_TOKEN", "").strip(),
        analysis_rate_limit=max(1, _env_int("ANALYSIS_RATE_LIMIT", 12)),
        label_rate_limit=max(1, _env_int("LABEL_RATE_LIMIT", 30)),
        capture_rate_limit=max(1, _env_int("CAPTURE_RATE_LIMIT", 600)),
        # Local convenience: show .env keys in the sidebar. Turn off for public deployments.
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
    )


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure the app logger once; Streamlit reruns must not stack handlers."""
    logger = logging.getLogger("skincare")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


PROVIDER_ENV_ALIASES = {"Gemini": ["GOOGLE_API_KEY"], "Hugging Face": ["HUGGINGFACEHUB_API_TOKEN", "HUGGING_FACE_TOKEN"], "Groq": []}


def get_env_value(key: str, aliases: list[str] | None = None) -> str:
    for candidate in [key, *(aliases or [])]:
        value = os.getenv(candidate, "").strip()
        if value:
            return value
    return ""
