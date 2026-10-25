# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from unittest.mock import MagicMock

import pytest
import requests
from PIL import Image

import vlm.engine as vlm_engine
from vlm.engine import VLMEngine, VLMOptions, VLMProviderError, normalize_vlm_json
from vlm.quality import check_vlm_output, quality_score
from vlm.router import ProviderHealth, ProviderTarget, ResponseCache, VLMRouter, describe_fallback


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def crop(tmp_path):
    path = tmp_path / "crop.jpg"
    Image.new("RGB", (64, 64), (200, 160, 140)).save(path)
    return path


def ok_output(provider):
    return {"provider": provider, "model": "m", "visible_observations": ["a", "b"], "care_suggestions": ["c", "d"], "disclaimer": "x"}


def scripted_engine(script):
    """script: provider -> exception or output; records calls."""
    engine = MagicMock()

    def analyze(provider, **_):
        engine.calls.append(provider)
        result = script[provider]
        if isinstance(result, Exception):
            raise result
        return dict(result)

    engine.calls = []
    engine.analyze.side_effect = analyze
    return engine


CHAIN = [ProviderTarget("Gemini", "g-key"), ProviderTarget("Groq", "q-key"), ProviderTarget("Hugging Face", "h-key")]


def test_falls_back_to_next_provider_and_explains(crop):
    engine = scripted_engine({"Gemini": VLMProviderError("429", "quota"), "Groq": VLMProviderError("expired", "auth"), "Hugging Face": ok_output("Hugging Face")})
    output, attempts = VLMRouter(engine).analyze(CHAIN, crop, {}, {})
    assert output["provider"] == "Hugging Face"
    assert [a["status"] for a in attempts] == ["failed", "failed", "ok"]
    note = describe_fallback(attempts, output["provider"])
    assert "Gemini (kota" in note and "Groq (anahtar" in note and note.endswith("Hugging Face ile üretildi.")


def test_failed_provider_is_benched_then_retried_after_cooldown(crop):
    clock = FakeClock()
    engine = scripted_engine({"Gemini": VLMProviderError("expired", "auth"), "Groq": ok_output("Groq")})
    router = VLMRouter(engine, ProviderHealth(clock), ResponseCache(clock=clock))
    chain = CHAIN[:2]
    router.analyze(chain, crop, {"summary": {"n": 1}}, {})
    _, attempts = router.analyze(chain, crop, {"summary": {"n": 2}}, {})  # different input: no cache hit
    assert attempts[0] == {"provider": "Gemini", "status": "skipped", "kind": "auth", "seconds_left": 1800}
    assert engine.calls == ["Gemini", "Groq", "Groq"]
    clock.now += 1801
    router.analyze(chain, crop, {"summary": {"n": 3}}, {})
    assert engine.calls[-2:] == ["Gemini", "Groq"]


def test_bad_personal_key_does_not_bench_another_credential(crop):
    engine = scripted_engine({"Gemini": VLMProviderError("expired", "auth"), "Groq": ok_output("Groq")})
    router = VLMRouter(engine)
    router.analyze([ProviderTarget("Gemini", "bad-personal-key"), CHAIN[1]], crop, {"summary": 1}, {})
    engine.analyze.side_effect = lambda provider, **_: ok_output(provider)
    output, attempts = router.analyze([ProviderTarget("Gemini", "server-key")], crop, {"summary": 2}, {})
    assert output["provider"] == "Gemini" and attempts[0]["status"] == "ok"


def test_quota_cooldown_respects_retry_after():
    clock = FakeClock()
    health = ProviderHealth(clock)
    health.mark_failure("Gemini", "quota", retry_after=300)
    assert health.blocked_reason("Gemini") == ("quota", 300)
    health.mark_failure("Groq", "bad_output")  # per-request problem: never benched
    assert health.blocked_reason("Groq") is None
    health.mark_success("Gemini")
    assert health.snapshot() == {}


def test_cache_hit_skips_providers_and_expires(crop):
    clock = FakeClock()
    engine = scripted_engine({"Gemini": ok_output("Gemini")})
    router = VLMRouter(engine, ProviderHealth(clock), ResponseCache(ttl_seconds=3600, clock=clock))
    first, _ = router.analyze(CHAIN[:1], crop, {"summary": 1}, {})
    second, attempts = router.analyze(CHAIN[:1], crop, {"summary": 1}, {})
    assert first["cached"] is False and second["cached"] is True
    assert attempts == [{"provider": "Gemini", "status": "cache"}]
    assert engine.calls == ["Gemini"]
    clock.now += 3601
    router.analyze(CHAIN[:1], crop, {"summary": 1}, {})
    assert engine.calls == ["Gemini", "Gemini"]


def test_cache_is_bounded():
    cache = ResponseCache(max_items=2)
    for key in "abc":
        cache.put(key, {"v": key})
    assert cache.get("a") is None and cache.get("c") == {"v": "c"}


def test_all_failed_raises_with_summary(crop):
    engine = scripted_engine({"Gemini": VLMProviderError("boom", "server")})
    chain = [CHAIN[0], ProviderTarget("Groq", "")]
    with pytest.raises(VLMProviderError) as info:
        VLMRouter(engine).analyze(chain, crop, {}, {})
    message = str(info.value)
    assert "Gemini: sağlayıcı geçici olarak yanıt vermiyor" in message
    assert "Groq: anahtar tanımlı değil" in message
    assert info.value.kind == "server"


@pytest.mark.parametrize(("status", "kind"), [(401, "auth"), (403, "auth"), (402, "credits"), (429, "quota"), (404, "config"), (503, "server")])
def test_http_errors_are_classified(monkeypatch, crop, status, kind):
    session = MagicMock()
    response = MagicMock(status_code=status, ok=False, text="{}", headers={"Retry-After": "12"})
    session.post.return_value = response
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    monkeypatch.setattr(vlm_engine, "_backoff", lambda *_: None)
    with pytest.raises(VLMProviderError) as info:
        VLMEngine(VLMOptions(max_retries=0)).analyze("Gemini", crop, "key-123456")
    assert info.value.kind == kind
    if kind == "quota":
        assert info.value.retry_after == 12.0


def test_network_error_kind(monkeypatch, crop):
    session = MagicMock()
    session.post.side_effect = requests.ConnectionError("down")
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    with pytest.raises(VLMProviderError) as info:
        VLMEngine(VLMOptions(max_retries=0)).analyze("Groq", crop, "key-123456")
    assert info.value.kind == "network"


def test_schema_coerces_and_rejects():
    output = normalize_vlm_json('{"visible_observations": "tek cümle", "care_suggestions": [1, " öneri ", ""]}', "X", "m")
    assert output["visible_observations"] == ["tek cümle"]
    assert output["care_suggestions"] == ["öneri"]
    assert output["prompt_version"] == vlm_engine.PROMPT_VERSION
    with pytest.raises(VLMProviderError) as info:
        normalize_vlm_json('{"visible_observations": [], "care_suggestions": [2]}', "X", "m")
    assert info.value.kind == "bad_output"


METRICS_GOOD = {"available": True, "overall_score": 82}
METRICS_BAD = {"available": True, "overall_score": 25}
REGIONS = {
    "most_affected": "left_cheek",
    "most_affected_name": "Sol yanak",
    "regions": [
        {"key": "forehead", "name": "Alın", "visible": False},
        {"key": "left_cheek", "name": "Sol yanak", "visible": True},
    ],
}


def vlm(observations, suggestions=("Nazik temizleyici kullan.", "Güneş koruyucu sür.")):
    return {"visible_observations": list(observations), "care_suggestions": list(suggestions), "safety_removed_count": 0}


def by_name(checks):
    return {c["check"]: c["ok"] for c in checks}


def test_quality_flags_exaggeration_and_understatement():
    loud = vlm(["Belirgin kızarıklık var.", "Yoğun nokta görünümü ve belirgin ton farkı."])
    assert by_name(check_vlm_output(loud, METRICS_GOOD))["severity"] is False
    calm = vlm(["Hafif kızarıklık var.", "Birkaç küçük nokta görünüyor."])
    assert by_name(check_vlm_output(calm, METRICS_GOOD))["severity"] is True
    assert by_name(check_vlm_output(calm, METRICS_BAD))["severity"] is False


def test_quality_region_checks():
    good = vlm(["Sol yanakta yoğunlaşan noktalar var.", "Alın bölgesi kadrajda görünmüyor."])
    checks = by_name(check_vlm_output(good, region_summary=REGIONS))
    assert checks["most_affected_region"] and checks["invisible_regions"]
    bad = vlm(["Alında küçük noktalar var.", "Burun çevresi kızarık."])
    checks = by_name(check_vlm_output(bad, region_summary=REGIONS))
    assert not checks["most_affected_region"] and not checks["invisible_regions"]


def test_quality_routine_conflict_and_score():
    routine = {"excluded": [{"name": "Retinol", "reason": "hamilelik"}]}
    output = vlm(["Hafif ton farkı var.", "Birkaç nokta var."], ["Akşamları retinol kullanabilirsin.", "Nemlendir."])
    checks = check_vlm_output(output, routine=routine)
    assert by_name(checks)["routine_conflict"] is False
    assert 0 < quality_score(checks) < 1


def _gemini_ok(text='{"visible_observations": ["a", "b"], "care_suggestions": ["c", "d"]}'):
    response = MagicMock(status_code=200, ok=True, headers={})
    response.json.return_value = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}
    return response


def _gemini_daily_quota():
    response = MagicMock(status_code=429, ok=False, headers={}, text='{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}')
    response.json.return_value = {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "45256s"}]}}
    return response


def test_gemini_falls_back_to_next_model_and_benches_exhausted_one(monkeypatch, crop):
    session = MagicMock()
    session.post.side_effect = [_gemini_daily_quota(), _gemini_ok(), _gemini_ok()]
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    options = VLMOptions(gemini_model="model-a", gemini_fallback_models=("model-b",), max_retries=0)
    output = VLMEngine(options).analyze("Gemini", crop, "key-123456")
    urls = [call.args[0] for call in session.post.call_args_list]
    assert "model-a" in urls[0] and "model-b" in urls[1]
    assert output["model"] == "model-b"
    kind, seconds_left = vlm_engine.GEMINI_MODEL_HEALTH.blocked_reason("model-a")
    assert kind == "quota" and seconds_left > 12 * 3600 - 5  # 45256 s capped at 12 h
    # Next request skips the exhausted model entirely.
    VLMEngine(options).analyze("Gemini", crop, "key-123456")
    assert "model-b" in session.post.call_args_list[2].args[0]


def test_gemini_auth_error_does_not_try_other_models(monkeypatch, crop):
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=401, ok=False, headers={}, text="{}")
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    options = VLMOptions(gemini_model="model-a", gemini_fallback_models=("model-b",), max_retries=0)
    with pytest.raises(VLMProviderError) as info:
        VLMEngine(options).analyze("Gemini", crop, "key-123456")
    assert info.value.kind == "auth"
    assert session.post.call_count == 1  # a bad key is bad for every model


def test_daily_quota_message_is_specific(monkeypatch, crop):
    session = MagicMock()
    session.post.return_value = _gemini_daily_quota()
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    with pytest.raises(VLMProviderError, match="günlük ücretsiz kotası"):
        VLMEngine(VLMOptions(gemini_fallback_models=(), max_retries=0)).analyze("Gemini", crop, "key-123456")


def test_region_check_handles_split_side_words():
    regions = {**REGIONS, "most_affected": "right_cheek", "most_affected_name": "Sağ yanak"}
    text = vlm(["Özellikle sağ ve sol yanak bölgesinde yoğunlaşan lekeler var.", "Alın kadrajda görünmüyor."])
    assert by_name(check_vlm_output(text, region_summary=regions))["most_affected_region"] is True
    other = vlm(["Sol yanakta noktalar var.", "Burun çevresi kızarık."])
    assert by_name(check_vlm_output(other, region_summary=regions))["most_affected_region"] is False
