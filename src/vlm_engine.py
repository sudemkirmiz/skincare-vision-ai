from __future__ import annotations

import base64
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import requests
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from health import ProviderHealth
from safety.safe_response_builder import DISCLAIMER, SafeResponseBuilder

logger = logging.getLogger("skincare.vlm")

HF_VISION_MODELS = [
    "google/gemma-3-4b-it",
    "google/gemma-3-12b-it",
    "google/gemma-3-27b-it",
    "Qwen/Qwen3-VL-30B-A3B-Instruct",
    "Qwen/Qwen2.5-VL-72B-Instruct",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "CohereLabs/aya-vision-32b",
]

# Bump when the analysis prompt changes: it is part of the cache key and of every output.
PROMPT_VERSION = "2026-10-24.4"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
# Free-tier quotas are per model, so other models on the same key are a real fallback.
DEFAULT_GEMINI_FALLBACK_MODELS = ("gemini-flash-lite-latest", "gemini-2.5-flash")
MODEL_FALLBACK_KINDS = {"quota", "config", "server"}
# Process-wide: a model that hit its daily quota stays benched across requests.
GEMINI_MODEL_HEALTH = ProviderHealth()
DEFAULT_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
VLM_MAX_IMAGE_SIDE = 1024
GEMINI_THINKING_BUDGET = 512
VLM_JPEG_QUALITY = 85
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_ITEMS = 8
MAX_ITEM_CHARS = 400

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "visible_observations": {"type": "ARRAY", "items": {"type": "STRING"}},
        "care_suggestions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "disclaimer": {"type": "STRING"},
    },
    "required": ["visible_observations", "care_suggestions", "disclaimer"],
}


class VLMProviderError(RuntimeError):
    """Provider failure with a machine-readable `kind` so the router can decide how to react.

    kinds: auth, credits, quota, network, server, config, blocked, bad_output, unknown
    """

    def __init__(self, message: str, kind: str = "unknown", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after

    def redacted(self, secret: str) -> VLMProviderError:
        return VLMProviderError(redact_secret(str(self), secret), self.kind, self.retry_after)


class VLMAnalysis(BaseModel):
    """Schema for the model's JSON. Lenient on input shape, strict on what comes out."""

    model_config = ConfigDict(extra="ignore")

    visible_observations: list[str] = Field(default_factory=list)
    care_suggestions: list[str] = Field(default_factory=list)

    @field_validator("visible_observations", "care_suggestions", mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        return ensure_string_list(value)

    @model_validator(mode="after")
    def _not_empty(self) -> VLMAnalysis:
        if not self.visible_observations and not self.care_suggestions:
            raise ValueError("gözlem/öneri alanları boş")
        return self


@dataclass(frozen=True)
class VLMOptions:
    gemini_model: str = DEFAULT_GEMINI_MODEL
    gemini_fallback_models: tuple[str, ...] = DEFAULT_GEMINI_FALLBACK_MODELS
    groq_model: str = DEFAULT_GROQ_MODEL
    timeout_seconds: float = 90.0
    max_retries: int = 2
    trust_env_proxy: bool = False


@dataclass(frozen=True)
class VLMRequest:
    provider: str
    image_base64: str
    image_data_url: str
    mime_type: str
    api_key: str
    yolo_json: dict[str, Any]
    quality_json: dict[str, Any]
    hf_model: str | None = None
    hf_provider: str | None = None
    # Overrides for non-analysis tasks (e.g. reading an ingredient label).
    prompt: str | None = None
    response_schema: dict[str, Any] | None = None

    @property
    def text_prompt(self) -> str:
        return self.prompt or build_safe_prompt(self.yolo_json, self.quality_json)

    def __repr__(self) -> str:  # never leak key or image bytes into logs
        return f"VLMRequest(provider={self.provider!r}, hf_model={self.hf_model!r})"


class VLMProvider(Protocol):
    def generate(self, request: VLMRequest) -> tuple[str, str]:
        """Return (raw model text, model id)."""
        ...

    def analyze(self, request: VLMRequest) -> dict[str, Any]:
        ...


class VLMEngine:
    def __init__(self, options: VLMOptions | None = None) -> None:
        self.options = options or VLMOptions()

    def analyze(
        self,
        provider: str,
        image_path: str | Path,
        api_key: str,
        yolo_json: dict[str, Any] | None = None,
        quality_json: dict[str, Any] | None = None,
        hf_model: str | None = None,
        hf_provider: str | None = None,
    ) -> dict[str, Any]:
        request = _build_request(
            provider, prepare_vlm_image(Path(image_path)), api_key, hf_model, hf_provider,
            yolo_json=compact_yolo_json(yolo_json), quality_json=quality_json or {},
        )
        provider_client = create_vlm_provider(provider, self.options)
        started = time.perf_counter()
        try:
            result = provider_client.analyze(request)
        except VLMProviderError as error:
            # Re-raise with any secret scrubbed from the message.
            raise error.redacted(request.api_key) from None
        logger.info(
            "VLM analysis done provider=%s model=%s elapsed=%.2fs removed_items=%s",
            result["provider"],
            result["model"],
            time.perf_counter() - started,
            result.get("safety_removed_count", 0),
        )
        return result

    def extract_ingredients(
        self,
        provider: str,
        image_bytes: bytes,
        api_key: str,
        hf_model: str | None = None,
        hf_provider: str | None = None,
    ) -> dict[str, Any]:
        """Read the INCI list from a product label photo. Output is untrusted text, parsed downstream."""
        request = _build_request(
            provider, prepare_label_image(image_bytes), api_key, hf_model, hf_provider,
            prompt=INGREDIENT_OCR_PROMPT, response_schema=INGREDIENT_OCR_SCHEMA,
        )
        try:
            text, model = create_vlm_provider(provider, self.options).generate(request)
        except VLMProviderError as error:
            raise error.redacted(request.api_key) from None
        try:
            data = json.loads(extract_json_object(strip_code_fence(text)))
        except json.JSONDecodeError:
            raise VLMProviderError("Etiket okunamadı; daha net ve düz bir fotoğraf deneyin.", "bad_output") from None
        ingredients = str(data.get("ingredients_text") or "").strip()[:4000]
        if not ingredients:
            raise VLMProviderError("Fotoğrafta içerik listesi bulunamadı. İçindekiler (Ingredients) bölümünü yakından çekin.", "bad_output")
        return {"ingredients_text": ingredients, "product_name": str(data.get("product_name") or "")[:120], "model": model}


    def chat(self, provider: str, system: str, messages: list[dict[str, str]], api_key: str,
             hf_model: str | None = None, hf_provider: str | None = None) -> tuple[str, str]:
        """Text-only conversation (skin coach). Returns (reply, model); the reply is untrusted text."""
        key = sanitize_api_key(api_key)
        if not key:
            raise VLMProviderError(f"{provider} için API anahtarı tanımlı değil.", "auth")
        target = create_vlm_provider(provider, self.options)
        try:
            if isinstance(target, HuggingFaceProvider):
                return target.chat(system, messages, key, hf_model, hf_provider)
            return target.chat(system, messages, key)
        except VLMProviderError as error:
            raise error.redacted(key) from None

    def detect_spots(self, provider: str, image_path: str | Path, api_key: str) -> list[dict[str, Any]]:
        """Second-opinion spot detection (Gemini only): raw [{"box_2d": [ymin, xmin, ymax, xmax]}] on a 0-1000 grid."""
        if provider.strip().lower() != "gemini":
            raise VLMProviderError("İkinci görüş tespiti yalnızca Gemini ile yapılır.", "config")
        request = _build_request(
            provider, prepare_vlm_image(Path(image_path)), api_key, None, None,
            prompt=SPOT_DETECTION_PROMPT, response_schema=SPOT_DETECTION_SCHEMA,
        )
        try:
            text, _ = create_vlm_provider(provider, self.options).generate(request)
        except VLMProviderError as error:
            raise error.redacted(request.api_key) from None
        try:
            data = json.loads(extract_json_object(strip_code_fence(text)))
        except json.JSONDecodeError:
            raise VLMProviderError("İkinci görüş yanıtı okunamadı.", "bad_output") from None
        spots = data.get("spots") if isinstance(data, dict) else None
        if not isinstance(spots, list):
            raise VLMProviderError("İkinci görüş yanıtı beklenen formatta değil.", "bad_output")
        return spots


def _build_request(
    provider: str,
    jpeg_bytes: bytes,
    api_key: str,
    hf_model: str | None,
    hf_provider: str | None,
    **extra: Any,
) -> VLMRequest:
    image_base64 = base64.b64encode(jpeg_bytes).decode("ascii")
    request = VLMRequest(
        provider=provider,
        image_base64=image_base64,
        image_data_url=f"data:image/jpeg;base64,{image_base64}",
        mime_type="image/jpeg",
        api_key=sanitize_api_key(api_key),
        yolo_json=extra.pop("yolo_json", {}),
        quality_json=extra.pop("quality_json", {}),
        hf_model=hf_model,
        hf_provider=hf_provider,
        **extra,
    )
    _validate_request(request)
    return request


class _HttpProvider:
    def __init__(self, options: VLMOptions) -> None:
        self.options = options

    def _post(self, name: str, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        session = requests.Session()
        session.trust_env = self.options.trust_env_proxy
        attempts = self.options.max_retries + 1
        try:
            for attempt in range(1, attempts + 1):
                try:
                    response = session.post(url, headers=headers, json=payload, timeout=self.options.timeout_seconds)
                except requests.RequestException as error:
                    if attempt < attempts:
                        _backoff(attempt, None)
                        continue
                    raise VLMProviderError(
                        f"{name} bağlantı hatası ({type(error).__name__}). Ağ, DNS, proxy veya güvenlik "
                        "duvarı erişimi engelliyor olabilir. Kurumsal proxy kullanıyorsanız VLM_TRUST_ENV_PROXY=true deneyin.",
                        "network",
                    ) from None

                if response.status_code in RETRYABLE_STATUS and attempt < attempts:
                    logger.warning("%s HTTP %s, retrying (%s/%s)", name, response.status_code, attempt, attempts - 1)
                    _backoff(attempt, response.headers.get("Retry-After"))
                    continue
                if not response.ok:
                    raise VLMProviderError(
                        _format_http_error(name, response),
                        _http_error_kind(response.status_code),
                        _retry_after_seconds(response.headers.get("Retry-After")) or _body_retry_delay(response),
                    )
                try:
                    return response.json()
                except ValueError:
                    raise VLMProviderError(f"{name} JSON olmayan yanıt döndürdü: {response.text[:500]}", "server") from None
        finally:
            session.close()
        raise VLMProviderError(f"{name} isteği tamamlanamadı.", "unknown")


class GeminiProvider(_HttpProvider):
    def analyze(self, request: VLMRequest) -> dict[str, Any]:
        text, model = self.generate(request)
        return normalize_vlm_json(text, provider="Gemini", model=model)

    def generate(self, request: VLMRequest) -> tuple[str, str]:
        return self._with_model_fallback(lambda model: self._generate_with_model(request, model))

    def chat(self, system: str, messages: list[dict[str, str]], api_key: str) -> tuple[str, str]:
        return self._with_model_fallback(lambda model: self._chat_with_model(system, messages, api_key, model))

    def _with_model_fallback(self, call) -> tuple[str, str]:
        """Try the configured model, then fallback models on quota/config/server errors."""
        models = list(dict.fromkeys([self.options.gemini_model, *self.options.gemini_fallback_models]))
        last_error: VLMProviderError | None = None
        for model in models:
            benched = GEMINI_MODEL_HEALTH.blocked_reason(model)
            if benched:
                last_error = last_error or VLMProviderError(f"Gemini {model} geçici olarak atlanıyor ({benched[0]}).", benched[0])
                continue
            try:
                result = call(model)
            except VLMProviderError as error:
                if error.kind not in MODEL_FALLBACK_KINDS:
                    raise
                GEMINI_MODEL_HEALTH.mark_failure(model, error.kind, error.retry_after)
                logger.warning("Gemini model %s failed (%s); trying next model", model, error.kind)
                last_error = error
                continue
            GEMINI_MODEL_HEALTH.mark_success(model)
            return result
        raise last_error or VLMProviderError("Gemini modeli bulunamadı.", "config")

    def _generate_with_model(self, request: VLMRequest, model: str) -> tuple[str, str]:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": request.text_prompt},
                        {"inline_data": {"mime_type": request.mime_type, "data": request.image_base64}},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                # 2.5 models count "thinking" tokens against this limit; a long prompt used to
                # exhaust it before any JSON was written. Cap thinking and leave room for the answer.
                "maxOutputTokens": 4096,
                "thinkingConfig": {"thinkingBudget": GEMINI_THINKING_BUDGET},
                "responseMimeType": "application/json",
                "responseSchema": request.response_schema or RESPONSE_SCHEMA,
            },
        }
        # Key goes in a header, never in the URL (URLs end up in exception text and logs).
        headers = {"x-goog-api-key": request.api_key, "Content-Type": "application/json"}
        data = self._post("Gemini", GEMINI_URL.format(model=model), headers, payload)

        try:
            candidate = data["candidates"][0]
            finish_reason = candidate.get("finishReason")
            text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            block_reason = (data.get("promptFeedback") or {}).get("blockReason") if isinstance(data, dict) else None
            if block_reason:
                raise VLMProviderError(f"Gemini isteği güvenlik filtresine takıldı: {block_reason}", "blocked") from None
            raise VLMProviderError(f"Gemini beklenmeyen yanıt döndürdü: {json.dumps(data)[:800]}", "bad_output") from None

        if finish_reason == "MAX_TOKENS":
            raise VLMProviderError("Gemini yanıtı token sınırında kesildi.", "bad_output")
        return text, model


    def _chat_with_model(self, system: str, messages: list[dict[str, str]], api_key: str, model: str) -> tuple[str, str]:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048, "thinkingConfig": {"thinkingBudget": 256}},
        }
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        data = self._post("Gemini", GEMINI_URL.format(model=model), headers, payload)
        try:
            candidate = data["candidates"][0]
            text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            block_reason = (data.get("promptFeedback") or {}).get("blockReason") if isinstance(data, dict) else None
            if block_reason:
                raise VLMProviderError(f"Gemini isteği güvenlik filtresine takıldı: {block_reason}", "blocked") from None
            raise VLMProviderError("Gemini beklenmeyen yanıt döndürdü.", "bad_output") from None
        if not text.strip():
            raise VLMProviderError("Gemini boş yanıt döndürdü.", "bad_output")
        return text, model


class _OpenAICompatibleProvider(_HttpProvider):
    name = ""
    url = ""

    def _chat(self, request: VLMRequest, model: str, json_mode: bool) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.text_prompt},
                        {"type": "image_url", "image_url": {"url": request.image_data_url}},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {request.api_key}", "Content-Type": "application/json"}
        data = self._post(self.name, self.url, headers, payload)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise VLMProviderError(f"{self.name} beklenmeyen yanıt döndürdü: {json.dumps(data)[:800]}", "bad_output") from None


    def _text_chat(self, system: str, messages: list[dict[str, str]], api_key: str, model: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *({"role": m["role"], "content": m["content"]} for m in messages)],
            "temperature": 0.4,
            "max_tokens": 800,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = self._post(self.name, self.url, headers, payload)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise VLMProviderError(f"{self.name} beklenmeyen yanıt döndürdü.", "bad_output") from None
        if not text.strip():
            raise VLMProviderError(f"{self.name} boş yanıt döndürdü.", "bad_output")
        return text


class HuggingFaceProvider(_OpenAICompatibleProvider):
    name = "Hugging Face Router"
    url = HF_ROUTER_URL

    def analyze(self, request: VLMRequest) -> dict[str, Any]:
        text, model = self.generate(request)
        return normalize_vlm_json(text, provider="Hugging Face", model=model)

    def generate(self, request: VLMRequest) -> tuple[str, str]:
        model = build_hf_router_model(request.hf_model or HF_VISION_MODELS[0], request.hf_provider)
        try:
            return self._chat(request, model, json_mode=False), model
        except VLMProviderError as error:
            raise VLMProviderError(
                f"{error}\n\nİpucu: Modelin hesabındaki Inference Providers ayarlarında etkin olduğunu, "
                f"lisansının kabul edildiğini ve token yetkisini kontrol edin. Model: {model}",
                error.kind,
                error.retry_after,
            ) from None

    def chat(self, system: str, messages: list[dict[str, str]], api_key: str, hf_model: str | None = None, hf_provider: str | None = None) -> tuple[str, str]:
        model = build_hf_router_model(hf_model or HF_VISION_MODELS[0], hf_provider)
        return self._text_chat(system, messages, api_key, model), model


class GroqProvider(_OpenAICompatibleProvider):
    name = "Groq"
    url = GROQ_URL

    def analyze(self, request: VLMRequest) -> dict[str, Any]:
        text, model = self.generate(request)
        return normalize_vlm_json(text, provider="Groq", model=model)

    def generate(self, request: VLMRequest) -> tuple[str, str]:
        model = self.options.groq_model
        return self._chat(request, model, json_mode=True), model

    def chat(self, system: str, messages: list[dict[str, str]], api_key: str) -> tuple[str, str]:
        model = self.options.groq_model
        return self._text_chat(system, messages, api_key, model), model


def build_hf_router_model(model: str, hf_provider: str | None = None) -> str:
    if ":" in model:
        return model
    if hf_provider and hf_provider != "auto":
        return f"{model}:{hf_provider}"
    return f"{model}:fastest"


def create_vlm_provider(provider: str, options: VLMOptions | None = None) -> VLMProvider:
    options = options or VLMOptions()
    normalized = provider.strip().lower()
    if normalized == "gemini":
        return GeminiProvider(options)
    if normalized in {"hugging face", "huggingface", "hf"}:
        return HuggingFaceProvider(options)
    if normalized == "groq":
        return GroqProvider(options)
    raise ValueError(f"Unsupported VLM provider: {provider}")


def compact_yolo_json(yolo_json: dict[str, Any] | None) -> dict[str, Any]:
    """Send the VLM only what it needs: fewer tokens, no local file paths."""
    if not yolo_json:
        return {}
    letterbox = yolo_json.get("letterbox") or {}
    findings = yolo_json.get("findings") or []
    compact: dict[str, Any] = {
        "image_size": [letterbox.get("original_width"), letterbox.get("original_height")],
        "confidence_threshold": yolo_json.get("confidence_threshold"),
        "summary": yolo_json.get("summary", {}),
        "findings": [
            {
                "confidence": item.get("confidence"),
                "box_xyxy": item.get("box_original_xyxy"),
                **({"region": item["region"]} if item.get("region") else {}),
            }
            for item in findings
            if isinstance(item, dict)
        ],
    }
    region_summary = yolo_json.get("region_summary")
    if region_summary:
        compact["regions"] = {
            region["name"]: {"count": region["count"], "density": region["density"]} if region["visible"] else "görünmüyor"
            for region in region_summary.get("regions", [])
        }
        compact["most_affected_region"] = region_summary.get("most_affected_name")
    if yolo_json.get("skin_metrics_summary"):
        compact["skin_metrics"] = yolo_json["skin_metrics_summary"]
    if yolo_json.get("routine_plan"):
        compact["routine_plan"] = yolo_json["routine_plan"]
    if yolo_json.get("user"):
        compact["user"] = yolo_json["user"]
    return compact


def build_safe_prompt(
    yolo_json: dict[str, Any] | None,
    quality_json: dict[str, Any] | None,
) -> str:
    return f"""
Sen bir tıbbi cihaz, doktor veya dermatolog DEĞİLSİN. Bir cilt bakım asistanısın.

Görev:
- Görseli ve YOLO JSON çıktısını birlikte değerlendir. YOLO kutuları yüz kırpımındaki piksel koordinatlarıdır.
- "regions" alanı varsa bölgesel dağılımı (alın, burun, yanaklar, çene; sol/sağ görsele göredir) yorumuna kat.
- YOLO küçük noktaları kaçırabilir; görselde açıkça görülen kızarıklık, parlama veya ton farkını da belirt.
- "skin_metrics" alanı görüntü işleme ile ölçülmüş 0-100 görsel indekslerdir (yüksek = daha iyi); düşük olan alanlara öncelik ver.
- Şiddet dilini skorlarla uyumlu tut: 75 ve üzeri "hafif/sınırlı", 55-74 "orta", 55 altı "belirgin". Abartma, küçültme.
- Metrik adlarını ve sayıları aynen kopyalama; doğal, sıcak ve sade Türkçe ile anlat.
- "user" alanı varsa kullanıcıya "hitap_adi" ile hitap et: ilk gözlem adıyla başlasın (örn. "Ayşe, ..."), sonra adı gereksiz tekrarlama.
  "hitap" "sen" ise ikinci tekil şahıs (cildin, kullanabilirsin), "siz" ise ikinci çoğul şahıs (cildiniz, kullanabilirsiniz) kullan; tüm cümlelerde tutarlı ol.
- "routine_plan" varsa bakım önerilerin bu planla çelişmesin; plandaki içerikleri tekrar listeleme, onları destekleyen alışkanlık önerileri ver. Ürün markası verme.
- Sadece kozmetik/bakım odaklı kısa Türkçe yorum üret (en fazla 5 gözlem, 5 öneri).
- Teşhis, hastalık adı, ilaç, etken madde dozu veya tedavi önerisi verme.
- Kesin neden söyleme; fotoğraftan neden belirlenemez.
- Ağrılı, yaygın, iz bırakan veya uzun süren durumda dermatoloğa danışılmasını söyle.
- Görselde yüz yoksa veya görsel uygun değilse bunu gözlem olarak belirt.

YOLO JSON:
{json.dumps(yolo_json or {}, ensure_ascii=False, separators=(",", ":"))}

Görüntü kalite sonucu:
{json.dumps(quality_json or {}, ensure_ascii=False, separators=(",", ":"))}

Yalnızca geçerli JSON döndür. Markdown, açıklama veya kod bloğu ekleme.
Şema:
{{"visible_observations":["..."],"care_suggestions":["..."],"disclaimer":"{DISCLAIMER}"}}
""".strip()


def normalize_vlm_json(response_text: str, provider: str, model: str) -> dict[str, Any]:
    cleaned = extract_json_object(strip_code_fence(response_text or ""))
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise VLMProviderError(f"{provider} geçerli JSON döndürmedi. Ham çıktı: {(response_text or '')[:800]}", "bad_output") from None
    if not isinstance(data, dict):
        raise VLMProviderError(f"{provider} JSON nesnesi yerine {type(data).__name__} döndürdü.", "bad_output")
    try:
        parsed = VLMAnalysis.model_validate(data)
    except ValidationError:
        raise VLMProviderError(f"{provider} JSON döndürdü ama gözlem/öneri alanları boş veya hatalı geldi.", "bad_output") from None

    # Model output is untrusted: always pass it through the safety filter and
    # always use our own disclaimer rather than whatever the model wrote.
    safe = SafeResponseBuilder().build(parsed.visible_observations, parsed.care_suggestions)
    return {
        "provider": provider,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "visible_observations": safe.visible_observations,
        "care_suggestions": safe.care_suggestions,
        "disclaimer": safe.disclaimer,
        "safety_removed_count": safe.removed_count,
    }


def strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", cleaned, flags=re.DOTALL)
    return match.group(1).strip() if match else cleaned


def extract_json_object(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return cleaned
    return cleaned[start : end + 1]


def ensure_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items = [item.strip()[:MAX_ITEM_CHARS] for item in value if isinstance(item, str) and item.strip()]
    return items[:MAX_ITEMS]


def sanitize_api_key(api_key: str) -> str:
    value = (api_key or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def redact_secret(text: str, secret: str) -> str:
    if secret and len(secret) >= 6:
        text = text.replace(secret, "***")
    # Defensive: scrub anything that looks like a key query param.
    return re.sub(r"(key=)[^&\s]+", r"\1***", text)


def _validate_request(request: VLMRequest) -> None:
    if not request.api_key:
        raise VLMProviderError(f"{request.provider} API anahtarı gerekli.", "auth")
    if not request.image_base64:
        raise VLMProviderError("Base64 görsel verisi oluşturulamadı.")


def _format_http_error(provider: str, response: requests.Response) -> str:
    detail = response.text[:800]
    hints = {
        401: "API anahtarı geçersiz, süresi dolmuş veya yetkisiz; sağlayıcı panelinden yeni anahtar oluşturun.",
        402: "Hesapta kredi kalmamış; sağlayıcı panelinden kredi yükleyin veya başka sağlayıcı seçin.",
        403: "Bu anahtarın modele erişim izni yok.",
        404: "Model bulunamadı; model adını kontrol edin (ör. GEMINI_MODEL / GROQ_MODEL).",
        429: "Kota veya hız sınırı aşıldı; biraz bekleyip tekrar deneyin.",
    }
    hint = hints.get(response.status_code, "")
    if response.status_code == 429 and "PerDay" in detail:
        hint = "Bu modelin günlük ücretsiz kotası doldu; yarın sıfırlanır veya faturalandırma açılabilir."
    if "expired" in detail.lower():
        hint = "API anahtarının süresi dolmuş; sağlayıcı panelinden yeni anahtar oluşturun."
    return f"{provider} HTTP {response.status_code} hatası. {hint}\n{detail}".strip()


def _http_error_kind(status: int) -> str:
    if status in {401, 403}:
        return "auth"
    if status == 402:
        return "credits"
    if status == 429:
        return "quota"
    if status in {400, 404, 422}:
        return "config"
    return "server" if status >= 500 else "unknown"


def _body_retry_delay(response: requests.Response) -> float | None:
    """Gemini puts the wait in the JSON body (RetryInfo.retryDelay, e.g. "45256s"), not in a header."""
    try:
        details = response.json().get("error", {}).get("details", [])
    except (ValueError, AttributeError):
        return None
    for detail in details if isinstance(details, list) else []:
        delay = detail.get("retryDelay") if isinstance(detail, dict) else None
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


def _retry_after_seconds(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _backoff(attempt: int, retry_after: str | None) -> None:
    # Jitter is scheduling noise, not a secret or security decision.
    delay = min(8.0, 0.8 * (2 ** (attempt - 1))) + random.uniform(0, 0.3)  # nosec B311
    if retry_after:
        try:
            delay = min(20.0, float(retry_after))
        except ValueError:
            pass
    time.sleep(delay)


INGREDIENT_OCR_PROMPT = """
Bu bir kozmetik ürün ambalajının fotoğrafı. Görevin yalnızca metni okumak:
- "Ingredients", "İçindekiler" veya "INCI" bölümündeki içerik listesini, ambalajdaki sırasıyla, virgülle ayırarak aynen yaz.
- Listeyi düzeltme, çevirme, yorumlama, içerik ekleme.
- Okuyamadığın kısımları atla; tahmin etme.
- Ürün adı görünüyorsa product_name alanına yaz, yoksa boş bırak.
Yalnızca JSON döndür: {"ingredients_text": "...", "product_name": "..."}
""".strip()
INGREDIENT_OCR_SCHEMA = {
    "type": "OBJECT",
    "properties": {"ingredients_text": {"type": "STRING"}, "product_name": {"type": "STRING"}},
    "required": ["ingredients_text"],
}
SPOT_DETECTION_PROMPT = """
Detect every visible acne-like spot on this facial skin photo: red or inflamed bumps (papules),
whiteheads/pustules, blackheads and small red marks left by blemishes.
Do NOT include freckles, moles, pores, hair, eyebrows, eyes, lips, nostrils, shadows or large evenly red areas.
Return one tight box per spot as box_2d = [ymin, xmin, ymax, xmax] normalised to 0-1000.
Return JSON only: {"spots": [{"box_2d": [ymin, xmin, ymax, xmax]}]}. Use an empty list if there are none.
""".strip()
SPOT_DETECTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "spots": {
            "type": "ARRAY",
            "items": {"type": "OBJECT", "properties": {"box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}}}, "required": ["box_2d"]},
        }
    },
    "required": ["spots"],
}
LABEL_MAX_IMAGE_SIDE = 1600  # small print needs more pixels than a face


def prepare_label_image(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((LABEL_MAX_IMAGE_SIDE, LABEL_MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def prepare_vlm_image(image_path: Path) -> bytes:
    if not image_path.exists():
        raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((VLM_MAX_IMAGE_SIDE, VLM_MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        # Re-encoding also strips EXIF/GPS metadata before the image leaves the machine.
        image.save(buffer, format="JPEG", quality=VLM_JPEG_QUALITY, optimize=True)
    return buffer.getvalue()
