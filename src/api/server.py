"""FastAPI backend for the React frontend.

Thin HTTP layer over the existing domain code in src/: no analysis logic lives here.
Provider API keys stay on the server; clients only learn whether a key exists.
Run: uvicorn api.server:app --app-dir src --port 8000
"""
from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from analysis.capture_guide import TARGETS, assess_frame
from analysis.change_map import ChangeMapError, build_change_map
from analysis.service import PROVIDER_ENV_KEYS
from api.container import Container
from api.rate_limit import RateLimiter
from api.schemas import CoachIn, EventIn, JournalIn, ProductCheckIn, ProfileIn, QuizIn, SaveAnalysisIn, ShelfItemIn
from api.security import RequestBodyLimitMiddleware
from coach import SUGGESTIONS, DailyLimiter, ask, build_context, clean_messages
from config import PROJECT_ROOT, PROVIDER_ENV_ALIASES, Settings, configure_logging, get_env_value, get_settings, load_env_file
from history.compare import compare_records, previous_record_comparison, trend_rows
from history.insights import FEMALE_ONLY_TRIGGERS, INSIGHT_WINDOW_DAYS, SKIN_FEEL, SYMPTOMS, TRIGGERS, build_insights
from history.store import EVENT_KINDS, record_from_payload, thumbnail_from_data_uri
from imaging import validate_image_bytes
from recommendation.catalog import recommend_products
from recommendation.engine import build_routine
from recommendation.inci import analyse_inci, evaluate_product, parse_inci
from recommendation.ingredients import INGREDIENTS
from recommendation.profile import (
    AGE_GROUPS,
    ALLERGIES,
    BUDGETS,
    CONCERNS,
    CURRENT_ACTIVES,
    MAKEUP,
    PREGNANCY,
    ROUTINE_SIZES,
    SENSITIVITY,
    SENSITIVITY_HELP,
    SKIN_TYPE_HELP,
    SKIN_TYPE_HINTS,
    SKIN_TYPES,
    SUN_EXPOSURE,
    SkinProfile,
)
from recommendation.shelf import CATEGORIES, USAGES, analyse_shelf
from report.filenames import report_filename
from report.pdf_report import build_pdf_report
from report.text_report import build_report_json, build_report_text
from users.profile import (
    ADDRESS_FORMS,
    CONSENT_TEXT,
    GENDERS,
    QUIZ,
    UserProfile,
    completeness,
    infer_skin_type,
    pregnancy_question_applies,
    profile_photo_mismatches,
    validate_required,
)
from vlm_engine import HF_VISION_MODELS, VLMEngine, VLMOptions, VLMProviderError
from vlm_router import KIND_LABELS
from weather import WeatherError, skin_tips, uv_band

logger = logging.getLogger("skincare.api")
PROVIDERS = ["Gemini", "Hugging Face", "Groq"]
MAX_VIEWS = 3
MAX_FRAME_BYTES = 1_500_000
MAX_FRAME_PIXELS = 2_000_000
JOURNAL_EDIT_DAYS = 30
MAX_SHELF_ITEMS = 40
INGREDIENT_IDS = {item.name: item.id for item in INGREDIENTS.values()}
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


# --- helpers ---------------------------------------------------------------
def profile_from_input(data: ProfileIn, existing: UserProfile | None = None) -> UserProfile:
    skin = data.skin
    pregnancy = "no" if data.gender == "male" else skin.pregnancy
    errors = validate_required(data.display_name, skin.age_group, skin.skin_type, skin.sensitivity, pregnancy, data.consent, data.gender)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    if not pregnancy_question_applies(data.gender):
        pregnancy = "no"
    base = existing.to_dict() if existing else {}
    return UserProfile(
        id=base.get("id") or UserProfile(display_name="x").id,
        created_at=base.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        consent_at=base.get("consent_at") or datetime.now().isoformat(timespec="seconds"),
        display_name=data.display_name,
        last_name=data.last_name,
        gender=data.gender or "other",
        address_form=data.address_form,
        answered=data.answered,
        skin=SkinProfile(
            skin_type=skin.skin_type or "unknown",
            sensitivity=skin.sensitivity or "no",
            age_group=skin.age_group or "18_29",
            pregnant_or_breastfeeding=pregnancy == "yes",
            pregnancy_disclosed=pregnancy != "undisclosed",
            concerns=skin.concerns,
            allergies=skin.allergies,
            current_actives=skin.current_actives,
            budget=skin.budget,
            routine_size=skin.routine_size,
            makeup=skin.makeup,
            sun_exposure=skin.sun_exposure,
        ),
    )


def profile_out(profile: UserProfile) -> dict[str, Any]:
    data = profile.to_dict()
    data["full_name"] = profile.full_name
    data["completeness"] = completeness(profile)
    data["skin"]["pregnancy"] = profile.skin.pregnancy_status
    return data


def provider_key(provider: str, typed_key: str | None, settings: Settings) -> str:
    if typed_key and settings.allow_user_api_keys:
        return typed_key.strip()
    return get_env_value(PROVIDER_ENV_KEYS[provider], PROVIDER_ENV_ALIASES[provider])


def hf_model_options(settings: Settings) -> list[str]:
    # A custom HF_VLM_MODEL from .env is offered even if it is not in the built-in list.
    return HF_VISION_MODELS if settings.hf_model in HF_VISION_MODELS else [settings.hf_model, *HF_VISION_MODELS]


def download(content: bytes | str, filename: str, media_type: str) -> Response:
    body = content.encode("utf-8") if isinstance(content, str) else content
    return Response(body, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    if settings is None:
        load_env_file(PROJECT_ROOT / ".env")
        settings = get_settings()
    configure_logging(settings.log_level)
    if settings.public_deployment and len(settings.app_access_token) < 32:
        raise RuntimeError("PUBLIC_DEPLOYMENT=true için en az 32 karakterli APP_ACCESS_TOKEN tanımlanmalıdır.")
    if settings.public_deployment and settings.allow_user_api_keys:
        raise RuntimeError("PUBLIC_DEPLOYMENT=true iken ALLOW_USER_API_KEYS=false olmalıdır.")
    services = container or Container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        services.close()

    app = FastAPI(
        title="SkinCare Vision AI API",
        version="2.0.0",
        lifespan=lifespan,
        docs_url=None if settings.public_deployment else "/docs",
        redoc_url=None if settings.public_deployment else "/redoc",
        openapi_url=None if settings.public_deployment else "/openapi.json",
    )
    app.state.container = services
    rate_limiter = RateLimiter()

    def harden_response(response: Response, path: str) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), geolocation=(self), microphone=()")
        if settings.public_deployment:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
                "form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'",
            )
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if path.startswith("/api/") and path != "/api/health":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.middleware("http")
    async def api_guard(request: Request, call_next):
        path = request.url.path
        protected = path.startswith("/api/") or (not settings.public_deployment and path in {"/docs", "/redoc", "/openapi.json"})
        if protected and path != "/api/health" and request.method != "OPTIONS" and settings.app_access_token:
            authorization = request.headers.get("authorization", "")
            scheme, _, supplied = authorization.partition(" ")
            valid = scheme.lower() == "bearer" and secrets.compare_digest(
                supplied.encode("utf-8"), settings.app_access_token.encode("utf-8")
            )
            if not valid:
                return harden_response(JSONResponse(
                    status_code=401,
                    content={"detail": "Bu uygulama için geçerli erişim anahtarı gerekli."},
                    headers={"WWW-Authenticate": "Bearer"},
                ), path)

        action_limits = {
            ("POST", "/api/analyses"): ("analysis", settings.analysis_rate_limit),
            ("POST", "/api/products/read-label"): ("label", settings.label_rate_limit),
            ("POST", "/api/coach"): ("coach", settings.label_rate_limit),
            ("POST", "/api/capture/check"): ("capture", settings.capture_rate_limit),
        }
        limited = action_limits.get((request.method, path))
        if limited:
            action, limit = limited
            subject = request.client.host if request.client else "unknown"
            allowed, retry_after = rate_limiter.take(subject, action, limit)
            if not allowed:
                return harden_response(JSONResponse(
                    status_code=429,
                    content={"detail": "İstek sınırına ulaşıldı; lütfen daha sonra tekrar deneyin."},
                    headers={"Retry-After": str(retry_after)},
                ), path)

        response = await call_next(request)
        return harden_response(response, path)

    # Dev server of the React app; in production the API serves the built frontend itself (same origin).
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
    if settings.public_deployment and "*" in origins:
        raise RuntimeError("PUBLIC_DEPLOYMENT=true iken CORS_ORIGINS joker karakter içeremez.")
    allowed_hosts = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
    if settings.public_deployment and "*" in allowed_hosts:
        raise RuntimeError("PUBLIC_DEPLOYMENT=true iken ALLOWED_HOSTS joker karakter içeremez.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Provider-Key"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_body_mb * 1024 * 1024)

    def get_profile(profile_id: str) -> UserProfile:
        data = services.store.get_profile(profile_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Profil bulunamadı.")
        return UserProfile.from_dict(data)

    def get_analysis(analysis_id: str, profile_id: str) -> tuple[dict[str, Any], UserProfile]:
        profile = get_profile(profile_id)
        payload = services.analyses.get(analysis_id, profile_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Analiz bulunamadı veya süresi doldu; lütfen yeniden analiz edin.")
        return payload, profile

    def with_routine(payload: dict[str, Any], profile: UserProfile) -> dict[str, Any]:
        """Routine always reflects the current profile, even for an earlier analysis."""
        return {**payload, "routine": build_routine(payload.get("skin_metrics"), profile.skin)}

    # --- meta ------------------------------------------------------------
    def readiness_details() -> tuple[bool, dict[str, Any]]:
        scoped_benches = services.service.router.health.snapshot()
        benched: dict[str, tuple[str, int]] = {}
        for scoped_name, reason in scoped_benches.items():
            name = scoped_name.split(":", 1)[0]
            if name not in benched or reason[1] > benched[name][1]:
                benched[name] = reason
        yolo_ready = settings.yolo_model_path.is_file() and settings.yolo_model_path.stat().st_size > 0
        database_ready = True
        database_error = None
        if settings.history_enabled:
            try:
                services.store.check()
            except Exception as error:
                logger.exception("Readiness database check failed")
                database_ready, database_error = False, type(error).__name__
        ready = yolo_ready and database_ready
        return ready, {
            "models": {"yolo": yolo_ready, "landmarks": settings.face_landmarker_path.is_file()},
            "database": {"ready": database_ready, "error": database_error},
            "providers": {
                name: {
                    "has_key": bool(get_env_value(PROVIDER_ENV_KEYS[name], PROVIDER_ENV_ALIASES[name])),
                    "benched": {"kind": benched[name][0], "label": KIND_LABELS.get(benched[name][0]), "seconds_left": benched[name][1]} if name in benched else None,
                }
                for name in PROVIDERS
            },
        }
    @app.get("/api/health")
    def health() -> Response:
        ready, _ = readiness_details()
        content = {"status": "ok" if ready else "degraded", "version": app.version, "ready": ready}
        return JSONResponse(status_code=200 if ready else 503, content=content)

    @app.get("/api/status")
    def status() -> Response:
        ready, details = readiness_details()
        content = {"status": "ok" if ready else "degraded", "version": app.version, "ready": ready, **details}
        return JSONResponse(status_code=200 if ready else 503, content=content)

    @app.get("/api/options")
    def options() -> dict[str, Any]:
        return {
            "skin_types": SKIN_TYPES, "skin_type_hints": SKIN_TYPE_HINTS, "skin_type_help": SKIN_TYPE_HELP,
            "sensitivity": SENSITIVITY, "sensitivity_help": SENSITIVITY_HELP, "concerns": CONCERNS, "age_groups": AGE_GROUPS,
            "genders": GENDERS, "pregnancy": PREGNANCY, "allergies": ALLERGIES, "current_actives": CURRENT_ACTIVES,
            "budgets": BUDGETS, "routine_sizes": ROUTINE_SIZES, "makeup": MAKEUP, "sun_exposure": SUN_EXPOSURE,
            "address_forms": ADDRESS_FORMS, "consent_text": CONSENT_TEXT, "event_kinds": EVENT_KINDS,
            "quiz": {key: {"question": question, "options": choices} for key, (question, choices) in QUIZ.items()},
            "journal": {"triggers": TRIGGERS, "symptoms": SYMPTOMS, "skin_feel": SKIN_FEEL, "female_only": sorted(FEMALE_ONLY_TRIGGERS)},
            "providers": PROVIDERS,
            "hf_models": hf_model_options(settings),
            "default_provider": os.getenv("VLM_PROVIDER", "Gemini") if os.getenv("VLM_PROVIDER", "Gemini") in PROVIDERS else "Gemini",
            "limits": {"max_upload_mb": settings.max_upload_mb, "max_views": MAX_VIEWS},
            "flags": {"history_enabled": settings.history_enabled, "second_opinion": settings.vlm_second_opinion, "allow_user_api_keys": settings.allow_user_api_keys},
        }

    @app.post("/api/quiz/skin-type")
    def quiz(answers: QuizIn) -> dict[str, Any]:
        skin_type = infer_skin_type(answers.t_zone, answers.cheeks, answers.blotting)
        return {"skin_type": skin_type, "label": SKIN_TYPES.get(skin_type) if skin_type else None}

    # --- profiles ----------------------------------------------------------
    @app.get("/api/profiles")
    def list_profiles() -> list[dict[str, Any]]:
        return [profile_out(UserProfile.from_dict(data)) for data in services.store.list_profiles()]

    @app.post("/api/profiles", status_code=201)
    def create_profile(data: ProfileIn) -> dict[str, Any]:
        profile = profile_from_input(data)
        services.store.save_profile(profile.to_dict())
        return profile_out(profile)

    @app.get("/api/profiles/{profile_id}")
    def read_profile(profile_id: str) -> dict[str, Any]:
        return profile_out(get_profile(profile_id))

    @app.put("/api/profiles/{profile_id}")
    def update_profile(profile_id: str, data: ProfileIn) -> dict[str, Any]:
        profile = profile_from_input(data, get_profile(profile_id))
        services.store.save_profile(profile.to_dict())
        return profile_out(profile)

    @app.post("/api/profiles/{profile_id}/touch", status_code=204)
    def touch_profile(profile_id: str) -> Response:
        get_profile(profile_id)
        services.store.touch_profile(profile_id)
        return Response(status_code=204)

    @app.delete("/api/profiles/{profile_id}", status_code=204)
    def delete_profile(profile_id: str) -> Response:
        get_profile(profile_id)
        services.store.delete_profile(profile_id)
        return Response(status_code=204)

    # --- analysis ------------------------------------------------------------
    @app.post("/api/analyses")
    def analyze(
        files: Annotated[list[UploadFile], File(description="1-3 photos of the same face")],
        profile_id: Annotated[str, Form()],
        provider: Annotated[str, Form()] = "Gemini",
        use_vlm: Annotated[bool, Form()] = True,
        second_opinion: Annotated[bool | None, Form()] = None,
        hf_model: Annotated[str | None, Form()] = None,
        x_provider_key: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        profile = get_profile(profile_id)
        if provider not in PROVIDERS:
            raise HTTPException(status_code=422, detail="Bilinmeyen yapay zekâ sağlayıcısı.")
        if hf_model and hf_model not in hf_model_options(settings):
            raise HTTPException(status_code=422, detail="Bilinmeyen Hugging Face modeli.")
        if not 1 <= len(files) <= MAX_VIEWS:
            raise HTTPException(status_code=422, detail=f"1 ile {MAX_VIEWS} arasında fotoğraf yükleyin.")
        images = []
        for upload in files:
            data = upload.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
            try:
                validate_image_bytes(data, settings.max_upload_mb, settings.max_image_pixels)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=f"{upload.filename}: {error}") from None
            images.append(data)
        fallback_keys = {name: get_env_value(PROVIDER_ENV_KEYS[name], PROVIDER_ENV_ALIASES[name]) for name in PROVIDERS}
        payload = services.service.analyze_views(
            images,
            provider=provider,
            api_key=provider_key(provider, x_provider_key, settings),
            hf_model=hf_model or settings.hf_model,
            use_vlm=use_vlm,
            profile=profile.skin,
            fallback_keys=fallback_keys,
            personalization=profile.vlm_personalization(),
            second_opinion=settings.vlm_second_opinion if second_opinion is None else second_opinion,
        )
        services.analyses.put(profile_id, payload)
        response = with_routine(payload, profile)
        response["mismatch_hints"] = profile_photo_mismatches(profile.skin, payload.get("skin_metrics"))
        return response

    @app.get("/api/analyses/{analysis_id}/routine")
    def routine(analysis_id: str, profile_id: str) -> dict[str, Any]:
        payload, profile = get_analysis(analysis_id, profile_id)
        return with_routine(payload, profile)["routine"]

    @app.get("/api/analyses/{analysis_id}/products")
    def products(analysis_id: str, profile_id: str) -> dict[str, Any]:
        payload, profile = get_analysis(analysis_id, profile_id)
        catalog = services.catalog()
        sections = recommend_products(with_routine(payload, profile)["routine"], profile.skin, catalog)
        return {"sections": sections, "catalog_errors": catalog.errors}

    @app.get("/api/analyses/{analysis_id}/report.{extension}")
    def report(analysis_id: str, extension: str, profile_id: str) -> Response:
        payload, profile = get_analysis(analysis_id, profile_id)
        full = with_routine(payload, profile)
        filename = report_filename(profile.full_name, payload.get("created_at"), extension)
        if extension == "txt":
            return download(build_report_text(full), filename, "text/plain; charset=utf-8")
        if extension == "json":
            return download(build_report_json(full), filename, "application/json")
        if extension != "pdf":
            raise HTTPException(status_code=404, detail="Desteklenmeyen rapor biçimi.")
        comparison, label = previous_record_comparison(services.store, full, profile_id) if settings.history_enabled else (None, None)
        pdf = build_pdf_report(full, profile, full["routine"], profile_photo_mismatches(profile.skin, payload.get("skin_metrics")), comparison, label)
        return download(pdf, filename, "application/pdf")

    @app.post("/api/analyses/{analysis_id}/save")
    def save(analysis_id: str, body: SaveAnalysisIn) -> dict[str, Any]:
        if not settings.history_enabled:
            raise HTTPException(status_code=403, detail="Geçmiş özelliği kapalı.")
        payload, profile = get_analysis(analysis_id, body.profile_id)
        thumbnail = thumbnail_from_data_uri(payload.get("face_thumbnail_uri")) if body.keep_thumbnail else None
        services.store.save(record_from_payload(with_routine(payload, profile), body.profile_id, note=body.note, thumbnail=thumbnail))
        return {"saved": True, "record_id": analysis_id}

    # --- history -------------------------------------------------------------
    def history_guard() -> None:
        if not settings.history_enabled:
            raise HTTPException(status_code=403, detail="Geçmiş özelliği kapalı.")

    @app.get("/api/profiles/{profile_id}/history")
    def history(profile_id: str) -> dict[str, Any]:
        history_guard()
        get_profile(profile_id)
        records = services.store.list(profile_id)
        return {
            "records": [{**record.to_export_dict(), "thumbnail_url": f"/api/history/{record.id}/thumbnail" if record.thumbnail else None} for record in records],
            "events": services.store.events(profile_id),
            "trend": trend_rows(records),
        }

    @app.get("/api/history/{record_id}/thumbnail")
    def thumbnail(record_id: str) -> Response:
        history_guard()
        record = services.store.get(record_id)
        if record is None or record.thumbnail is None:
            raise HTTPException(status_code=404, detail="Önizleme yok.")
        return Response(record.thumbnail, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

    @app.delete("/api/history/{record_id}", status_code=204)
    def delete_record(record_id: str) -> Response:
        history_guard()
        services.store.delete(record_id)
        return Response(status_code=204)

    @app.get("/api/profiles/{profile_id}/compare")
    def compare(profile_id: str, before: str, after: str) -> dict[str, Any]:
        history_guard()
        records = {record.id: record for record in services.store.list(profile_id)}
        if before not in records or after not in records:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
        first, second = sorted([records[before], records[after]], key=lambda record: record.created_at)
        return compare_records(first, second)

    @app.get("/api/profiles/{profile_id}/compare/map")
    def compare_map(profile_id: str, before: str, after: str) -> dict[str, Any]:
        history_guard()
        records = {record.id: record for record in services.store.list(profile_id)}
        if before not in records or after not in records or before == after:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
        first, second = sorted([records[before], records[after]], key=lambda record: record.created_at)
        if first.thumbnail is None or second.thumbnail is None:
            raise HTTPException(status_code=422, detail="Fark haritası için iki kaydın da yüz önizlemesi kaydedilmiş olmalı.")
        try:
            return build_change_map(first.thumbnail, second.thumbnail, services.landmarks,
                                    (first.head_pose or {}).get("yaw"), (second.head_pose or {}).get("yaw"))
        except ChangeMapError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    # --- daily journal -------------------------------------------------------
    def journal_day(value: str) -> str:
        try:
            day = date.fromisoformat(value)
        except ValueError:
            raise HTTPException(status_code=422, detail="Geçersiz tarih.") from None
        if day > date.today() or day < date.today() - timedelta(days=JOURNAL_EDIT_DAYS):
            raise HTTPException(status_code=422, detail=f"Yalnızca son {JOURNAL_EDIT_DAYS} günün kaydı düzenlenebilir.")
        return day.isoformat()

    def journal_summary(profile_id: str) -> dict[str, Any]:
        since = (date.today() - timedelta(days=INSIGHT_WINDOW_DAYS)).isoformat()
        entries = services.store.journal(profile_id, since)
        records = services.store.list(profile_id)
        # Evening actives to tick come from the latest saved routine.
        latest_actives = next((record.routine_actives for record in reversed(records) if record.routine_actives), [])
        return {"entries": entries, "summary": build_insights(entries, records), "routine_actives": latest_actives}

    @app.get("/api/profiles/{profile_id}/journal")
    def journal(profile_id: str) -> dict[str, Any]:
        history_guard()
        get_profile(profile_id)
        return journal_summary(profile_id)

    @app.put("/api/profiles/{profile_id}/journal/{day}")
    def save_journal(profile_id: str, day: str, entry: JournalIn) -> dict[str, Any]:
        history_guard()
        profile = get_profile(profile_id)
        unknown = [key for key in entry.triggers if key not in TRIGGERS] + [key for key in entry.symptoms if key not in SYMPTOMS]
        if unknown:
            raise HTTPException(status_code=422, detail="Bilinmeyen seçim: " + ", ".join(unknown))
        if profile.gender != "female" and set(entry.triggers) & FEMALE_ONLY_TRIGGERS:
            raise HTTPException(status_code=422, detail="Bu seçim profilinize uygun değil.")
        data = entry.model_dump()
        data["actives"] = [active.strip()[:40] for active in entry.actives if active.strip()]
        services.store.save_journal(profile_id, journal_day(day), data)
        return journal_summary(profile_id)

    @app.delete("/api/profiles/{profile_id}/journal/{day}")
    def delete_journal(profile_id: str, day: str) -> dict[str, Any]:
        history_guard()
        get_profile(profile_id)
        services.store.delete_journal(profile_id, journal_day(day))
        return journal_summary(profile_id)

    # --- product shelf -----------------------------------------------------
    def shelf_summary(profile_id: str, profile: UserProfile) -> dict[str, Any]:
        records = services.store.list(profile_id)
        # The latest saved routine tells which recommended actives the shelf still lacks.
        names = next((record.routine_actives for record in reversed(records) if record.routine_actives), [])
        routine = {"actives": [{"id": INGREDIENT_IDS[name], "name": name} for name in names if name in INGREDIENT_IDS]}
        return analyse_shelf(services.store.shelf(profile_id), profile.skin, routine)

    def shelf_item(body: ShelfItemIn) -> dict[str, Any]:
        if body.category not in CATEGORIES or body.usage not in USAGES:
            raise HTTPException(status_code=422, detail="Geçersiz kategori veya kullanım zamanı.")
        if body.opened_at:
            try:
                opened = date.fromisoformat(body.opened_at)
            except ValueError:
                raise HTTPException(status_code=422, detail="Geçersiz açılış tarihi.") from None
            if opened > date.today():
                raise HTTPException(status_code=422, detail="Açılış tarihi ileri bir tarih olamaz.")
        return body.model_dump()

    @app.get("/api/profiles/{profile_id}/shelf")
    def shelf(profile_id: str) -> dict[str, Any]:
        history_guard()
        return shelf_summary(profile_id, get_profile(profile_id))

    @app.post("/api/profiles/{profile_id}/shelf", status_code=201)
    def add_shelf_item(profile_id: str, body: ShelfItemIn) -> dict[str, Any]:
        history_guard()
        profile = get_profile(profile_id)
        if len(services.store.shelf(profile_id)) >= MAX_SHELF_ITEMS:
            raise HTTPException(status_code=422, detail=f"Rafınızda en fazla {MAX_SHELF_ITEMS} ürün olabilir.")
        services.store.save_shelf_item(profile_id, shelf_item(body))
        return shelf_summary(profile_id, profile)

    @app.put("/api/profiles/{profile_id}/shelf/{item_id}")
    def update_shelf_item(profile_id: str, item_id: str, body: ShelfItemIn) -> dict[str, Any]:
        history_guard()
        profile = get_profile(profile_id)
        existing = services.store.shelf_item(profile_id, item_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
        services.store.save_shelf_item(profile_id, {**shelf_item(body), "created_at": existing["created_at"]}, item_id)
        return shelf_summary(profile_id, profile)

    @app.delete("/api/profiles/{profile_id}/shelf/{item_id}")
    def delete_shelf_item(profile_id: str, item_id: str) -> dict[str, Any]:
        history_guard()
        profile = get_profile(profile_id)
        services.store.delete_shelf_item(profile_id, item_id)
        return shelf_summary(profile_id, profile)

    @app.post("/api/profiles/{profile_id}/events", status_code=201)
    def add_event(profile_id: str, event: EventIn) -> dict[str, Any]:
        history_guard()
        get_profile(profile_id)
        try:
            event_id = services.store.add_event(profile_id, event.kind, event.date, event.note)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        return {"id": event_id}

    @app.delete("/api/events/{event_id}", status_code=204)
    def delete_event(event_id: str) -> Response:
        history_guard()
        services.store.delete_event(event_id)
        return Response(status_code=204)

    @app.get("/api/profiles/{profile_id}/history/export.{extension}")
    def export(profile_id: str, extension: str) -> Response:
        history_guard()
        profile = get_profile(profile_id)
        filename = report_filename(profile.full_name, None, extension, prefix="Cilt_Gecmisi")
        if extension == "json":
            return download(services.store.export_json(profile_id), filename, "application/json")
        if extension == "csv":
            return download(services.store.export_csv(profile_id), filename, "text/csv; charset=utf-8")
        raise HTTPException(status_code=404, detail="Desteklenmeyen biçim.")

    @app.delete("/api/profiles/{profile_id}/history", status_code=200)
    def delete_history(profile_id: str) -> dict[str, int]:
        history_guard()
        get_profile(profile_id)
        return {"deleted": services.store.delete_person(profile_id)}

    # --- products ------------------------------------------------------------
    @app.post("/api/products/check")
    def check_product(body: ProductCheckIn) -> dict[str, Any]:
        profile = get_profile(body.profile_id)
        ingredients = parse_inci(body.inci_text)
        if len(ingredients) < 2:
            raise HTTPException(status_code=422, detail="Liste çok kısa görünüyor; içerikleri virgülle ayırarak yapıştırın.")
        payload = services.analyses.get(body.analysis_id, body.profile_id) if body.analysis_id else None
        routine_data = build_routine(payload.get("skin_metrics") if payload else None, profile.skin)
        return evaluate_product(analyse_inci(ingredients), profile.skin, routine_data)

    @app.post("/api/products/read-label")
    def read_label(
        file: Annotated[UploadFile, File()],
        provider: Annotated[str, Form()] = "Gemini",
        x_provider_key: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        if provider not in PROVIDERS:
            raise HTTPException(status_code=422, detail="Bilinmeyen yapay zekâ sağlayıcısı.")
        data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        try:
            validate_image_bytes(data, settings.max_upload_mb, settings.max_image_pixels)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        key = provider_key(provider, x_provider_key, settings)
        if not key:
            raise HTTPException(status_code=422, detail=f"Etiket okumak için {PROVIDER_ENV_KEYS[provider]} gerekli.")
        engine = VLMEngine(VLMOptions(
            gemini_model=settings.gemini_model, gemini_fallback_models=settings.gemini_fallback_models, groq_model=settings.groq_model,
            timeout_seconds=settings.vlm_timeout_seconds, max_retries=settings.vlm_max_retries, trust_env_proxy=settings.vlm_trust_env_proxy,
        ))
        try:
            return engine.extract_ingredients(provider, data, key, settings.hf_model, settings.hf_provider)
        except VLMProviderError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None

    @app.exception_handler(Exception)
    async def unexpected(_, error: Exception) -> JSONResponse:
        logger.exception("Unhandled API error")
        return JSONResponse(status_code=500, content={"detail": "Beklenmeyen bir hata oluştu; lütfen tekrar deneyin."})

    # --- skin coach ------------------------------------------------------------
    coach_limiter = DailyLimiter()

    @app.get("/api/coach/suggestions")
    def coach_suggestions() -> list[str]:
        return SUGGESTIONS

    @app.post("/api/coach")
    def coach(body: CoachIn, x_provider_key: Annotated[str | None, Header()] = None) -> dict[str, Any]:
        profile = get_profile(body.profile_id)
        if body.provider not in PROVIDERS:
            raise HTTPException(status_code=422, detail="Bilinmeyen yapay zekâ sağlayıcısı.")
        try:
            messages = clean_messages([message.model_dump() for message in body.messages])
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        chain = [(body.provider, provider_key(body.provider, x_provider_key, settings))]
        if settings.vlm_fallback:
            chain += [(name, get_env_value(PROVIDER_ENV_KEYS[name], PROVIDER_ENV_ALIASES[name])) for name in settings.vlm_fallback_order if name != body.provider]
        chain = [(name, key) for name, key in chain if key.strip()]
        if not chain:
            raise HTTPException(status_code=503, detail="Cilt koçu için tanımlı bir yapay zekâ anahtarı yok.")
        remaining = coach_limiter.take(body.profile_id)
        if remaining is None:
            raise HTTPException(status_code=429, detail="Bugünkü cilt koçu mesaj sınırına ulaştınız; yarın tekrar deneyebilirsiniz.")
        latest = shelf_data = journal_data = None
        if settings.history_enabled:
            latest = next((record for record in reversed(services.store.list(profile.id)) if record.overall_score is not None), None)
            shelf_data = shelf_summary(profile.id, profile)
            journal_data = journal_summary(profile.id)
        system = build_context(profile, latest, shelf_data, journal_data, body.weather.model_dump() if body.weather else None)
        engine = VLMEngine(VLMOptions(
            gemini_model=settings.gemini_model, gemini_fallback_models=settings.gemini_fallback_models, groq_model=settings.groq_model,
            timeout_seconds=settings.vlm_timeout_seconds, max_retries=settings.vlm_max_retries, trust_env_proxy=settings.vlm_trust_env_proxy,
        ))
        try:
            result = ask(engine, chain, system, messages, settings.hf_model, settings.hf_provider)
        except VLMProviderError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None
        return {**result, "remaining": remaining}

    # --- weather ---------------------------------------------------------------
    @app.get("/api/weather/search")
    def weather_search(q: Annotated[str, Query(max_length=60)]) -> list[dict[str, Any]]:
        try:
            return services.weather.search(q)
        except WeatherError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None

    @app.get("/api/weather")
    def weather_today(lat: Annotated[float, Query(ge=-90, le=90)], lon: Annotated[float, Query(ge=-180, le=180)],
                      profile_id: str | None = None) -> dict[str, Any]:
        profile = get_profile(profile_id) if profile_id else None
        try:
            weather = services.weather.today(lat, lon)
        except WeatherError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None
        skin = profile.skin if profile else SkinProfile()
        actives = list(skin.current_actives)
        if profile and settings.history_enabled:
            names = next((record.routine_actives for record in reversed(services.store.list(profile.id)) if record.routine_actives), [])
            actives += [INGREDIENT_IDS[name] for name in names if name in INGREDIENT_IDS]
        return {**weather, "uv_band": uv_band(weather["uv_max"]), "tips": skin_tips(weather, skin, actives), "source": "Open-Meteo"}

    # --- guided capture --------------------------------------------------------
    @app.post("/api/capture/check")
    def capture_check(
        frame: Annotated[UploadFile, File()],
        target: Annotated[str, Form()] = "front",
        avoid_sign: Annotated[int, Form()] = 0,
    ) -> dict[str, Any]:
        # Live preview frames are small, analysed in memory and never stored.
        if target not in TARGETS or avoid_sign not in (-1, 0, 1):
            raise HTTPException(status_code=422, detail="Geçersiz çekim hedefi.")
        data = frame.file.read(MAX_FRAME_BYTES + 1)
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(status_code=413, detail="Önizleme karesi çok büyük.")
        try:
            validate_image_bytes(data, 2, MAX_FRAME_PIXELS)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=422, detail="Önizleme karesi okunamadı.")
        return assess_frame(image, services.landmarks, target, avoid_sign)

    # --- frontend (built React app) --------------------------------------------
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                # Unknown API routes stay JSON 404s instead of silently returning the app shell.
                raise HTTPException(status_code=404, detail="Böyle bir API adresi yok.")
            if settings.public_deployment and path in {"docs", "redoc", "openapi.json"}:
                raise HTTPException(status_code=404, detail="Böyle bir adres yok.")
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
