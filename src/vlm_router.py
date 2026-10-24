"""Resilient VLM access: provider fallback chain, provider health (circuit breaker) and a response cache.

- Fallback: if the chosen provider fails (quota, expired key, outage, bad output), the next
  provider that has a key is tried, so users still get a comment.
- Health: a provider that just failed with a lasting cause is skipped for a cooldown instead
  of being called (and waited on) for every request. Expired keys stay benched longest.
- Cache: identical inputs (same face crop, findings, prompt version, requested provider)
  return the previous answer for an hour, saving quota and time on re-runs.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from health import ProviderHealth
from vlm_engine import PROMPT_VERSION, VLMEngine, VLMProviderError, compact_yolo_json

logger = logging.getLogger("skincare.vlm_router")

KIND_LABELS = {
    "auth": "anahtar geçersiz veya süresi dolmuş",
    "credits": "hesapta kredi yok",
    "quota": "kota/hız sınırı doldu",
    "network": "bağlantı kurulamadı",
    "server": "sağlayıcı geçici olarak yanıt vermiyor",
    "config": "model veya istek ayarı hatalı",
    "blocked": "istek güvenlik filtresine takıldı",
    "bad_output": "yanıt beklenen formatta gelmedi",
    "unknown": "bilinmeyen hata",
    "missing_key": "anahtar tanımlı değil",
}


class ResponseCache:
    def __init__(self, max_items: int = 128, ttl_seconds: float = 3600, clock=time.monotonic) -> None:
        self._items: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_items = max_items
        self._ttl = ttl_seconds
        self._clock = clock

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at > self._ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return dict(value)

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._items[key] = (self._clock(), dict(value))
            self._items.move_to_end(key)
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)


@dataclass(frozen=True)
class ProviderTarget:
    provider: str
    api_key: str
    hf_model: str | None = None


def cache_key(image_path: Path, provider: str, hf_model: str | None, yolo_json: dict | None, quality_json: dict | None) -> str:
    digest = hashlib.sha256()
    digest.update(Path(image_path).read_bytes())
    payload = {
        "provider": provider,
        "hf_model": hf_model,
        "prompt": PROMPT_VERSION,
        "yolo": compact_yolo_json(yolo_json),
        "quality": quality_json or {},
    }
    digest.update(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    return digest.hexdigest()


def health_key(target: ProviderTarget) -> str:
    """Scope cooldowns to a credential so one bad personal key cannot bench everyone."""
    fingerprint = hashlib.sha256(target.api_key.strip().encode("utf-8")).hexdigest()[:16]
    return f"{target.provider}:{fingerprint}"


class VLMRouter:
    def __init__(self, engine: VLMEngine, health: ProviderHealth | None = None, cache: ResponseCache | None = None) -> None:
        self.engine = engine
        self.health = health or ProviderHealth()
        self.cache = cache or ResponseCache()

    def analyze(
        self,
        chain: list[ProviderTarget],
        image_path: Path,
        yolo_json: dict[str, Any] | None,
        quality_json: dict[str, Any] | None,
        hf_provider: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Returns (output, attempts). Raises VLMProviderError when every provider failed."""
        if not chain:
            raise VLMProviderError("Hiçbir VLM sağlayıcısı için anahtar tanımlı değil.", "auth")
        requested = chain[0]
        key = cache_key(image_path, requested.provider, requested.hf_model, yolo_json, quality_json)
        cached = self.cache.get(key)
        if cached is not None:
            cached["cached"] = True
            return cached, [{"provider": cached["provider"], "status": "cache"}]

        attempts: list[dict[str, Any]] = []
        for target in chain:
            if not target.api_key.strip():
                attempts.append({"provider": target.provider, "status": "skipped", "kind": "missing_key"})
                continue
            scoped_health_key = health_key(target)
            benched = self.health.blocked_reason(scoped_health_key)
            if benched:
                kind, seconds_left = benched
                attempts.append({"provider": target.provider, "status": "skipped", "kind": kind, "seconds_left": seconds_left})
                continue
            started = time.perf_counter()
            try:
                output = self.engine.analyze(
                    provider=target.provider,
                    image_path=image_path,
                    api_key=target.api_key,
                    yolo_json=yolo_json,
                    quality_json=quality_json,
                    hf_model=target.hf_model,
                    hf_provider=hf_provider,
                )
            except VLMProviderError as error:
                self.health.mark_failure(scoped_health_key, error.kind, error.retry_after)
                attempts.append({
                    "provider": target.provider, "status": "failed", "kind": error.kind,
                    "error": str(error)[:300], "seconds": round(time.perf_counter() - started, 2),
                })
                logger.warning("VLM provider failed provider=%s kind=%s", target.provider, error.kind)
                continue
            self.health.mark_success(scoped_health_key)
            attempts.append({"provider": target.provider, "status": "ok", "seconds": round(time.perf_counter() - started, 2)})
            output["cached"] = False
            self.cache.put(key, output)
            return output, attempts

        raise VLMProviderError(describe_failure(attempts), _dominant_kind(attempts))


def _dominant_kind(attempts: list[dict[str, Any]]) -> str:
    kinds = [a.get("kind") for a in attempts if a.get("kind") and a.get("kind") != "missing_key"]
    return kinds[0] if kinds else "auth"


def describe_failure(attempts: list[dict[str, Any]]) -> str:
    lines = ["Hiçbir VLM sağlayıcısından yorum alınamadı:"]
    for attempt in attempts:
        label = KIND_LABELS.get(attempt.get("kind", "unknown"), attempt.get("kind", ""))
        suffix = " (geçici olarak atlandı)" if attempt["status"] == "skipped" and attempt.get("kind") != "missing_key" else ""
        lines.append(f"- {attempt['provider']}: {label}{suffix}")
    first_error = next((a.get("error") for a in attempts if a.get("error")), None)
    if first_error:
        lines.append("")
        lines.append(first_error)
    return "\n".join(lines)


def describe_fallback(attempts: list[dict[str, Any]], used_provider: str) -> str | None:
    """User-facing note when the comment came from a different provider than requested."""
    failed = [a for a in attempts if a["status"] in {"failed", "skipped"} and a.get("kind") != "missing_key"]
    if not failed:
        return None
    reasons = ", ".join(f"{a['provider']} ({KIND_LABELS.get(a.get('kind', 'unknown'), '')})" for a in failed)
    return f"{reasons} kullanılamadığı için yorum {used_provider} ile üretildi."
