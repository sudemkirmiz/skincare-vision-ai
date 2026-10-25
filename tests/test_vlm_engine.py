# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

import base64
import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
import requests
from PIL import Image

import vlm.engine as vlm_engine
from vlm.engine import (
    VLMEngine,
    VLMOptions,
    VLMProviderError,
    build_hf_router_model,
    compact_yolo_json,
    normalize_vlm_json,
    redact_secret,
    strip_code_fence,
)

SECRET = "AIzaSy-test-secret-123456"


@pytest.fixture
def face_image(tmp_path):
    path = tmp_path / "face.jpg"
    Image.new("RGB", (2000, 1500), (200, 160, 140)).save(path)
    return path


def _response(status: int, body: dict) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    response.ok = 200 <= status < 300
    response.json.return_value = body
    response.text = json.dumps(body)
    response.headers = {}
    return response


def _gemini_body(payload: dict) -> dict:
    text = json.dumps(payload, ensure_ascii=False)
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def fake_session(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    monkeypatch.setattr(vlm_engine, "_backoff", lambda *_: None)
    return session


def test_gemini_key_in_header_not_url_and_output_filtered(face_image, fake_session):
    fake_session.post.return_value = _response(
        200,
        _gemini_body({
            "visible_observations": ["Hafif parlama görünümü var.", "Rosacea olabilir."],
            "care_suggestions": ["Nazik temizleyici tercih edilebilir."],
            "disclaimer": "model disclaimer",
        }),
    )
    result = VLMEngine().analyze("Gemini", face_image, SECRET, yolo_json={}, quality_json={})

    url = fake_session.post.call_args.args[0]
    headers = fake_session.post.call_args.kwargs["headers"]
    assert SECRET not in url
    assert headers["x-goog-api-key"] == SECRET
    assert fake_session.trust_env is False
    assert result["visible_observations"] == ["Hafif parlama görünümü var."]
    assert result["safety_removed_count"] == 1
    assert result["disclaimer"] != "model disclaimer"


def test_retries_on_429_then_succeeds(face_image, fake_session):
    ok = _response(200, _gemini_body({"visible_observations": ["a"], "care_suggestions": ["b"], "disclaimer": ""}))
    fake_session.post.side_effect = [_response(429, {"error": "rate"}), ok]
    result = VLMEngine(VLMOptions(max_retries=2)).analyze("Gemini", face_image, SECRET)
    assert fake_session.post.call_count == 2
    assert result["care_suggestions"] == ["b"]


def test_http_error_never_leaks_key(face_image, fake_session):
    fake_session.post.return_value = _response(401, {"error": f"bad key {SECRET}"})
    with pytest.raises(VLMProviderError) as info:
        VLMEngine(VLMOptions(max_retries=0)).analyze("Gemini", face_image, SECRET)
    assert SECRET not in str(info.value)
    assert "401" in str(info.value)


def test_connection_error_never_leaks_key(face_image, fake_session):
    fake_session.post.side_effect = requests.ConnectionError(f"https://x/?key={SECRET}")
    with pytest.raises(VLMProviderError) as info:
        VLMEngine(VLMOptions(max_retries=1)).analyze("Gemini", face_image, SECRET)
    assert SECRET not in str(info.value)
    assert fake_session.post.call_count == 2


def test_groq_uses_openai_compatible_rest(face_image, fake_session):
    content = json.dumps({"visible_observations": ["x"], "care_suggestions": ["y"], "disclaimer": ""})
    fake_session.post.return_value = _response(200, {"choices": [{"message": {"content": content}}]})
    result = VLMEngine(VLMOptions(groq_model="some/groq-model")).analyze("Groq", face_image, "gsk_test_key")
    payload = fake_session.post.call_args.kwargs["json"]
    assert fake_session.post.call_args.args[0] == vlm_engine.GROQ_URL
    assert payload["model"] == "some/groq-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert result["model"] == "some/groq-model"


def test_image_is_downscaled_before_upload(face_image, fake_session):
    fake_session.post.return_value = _response(
        200, _gemini_body({"visible_observations": ["a"], "care_suggestions": [], "disclaimer": ""})
    )
    VLMEngine().analyze("Gemini", face_image, SECRET)
    data = fake_session.post.call_args.kwargs["json"]["contents"][0]["parts"][1]["inline_data"]["data"]
    with Image.open(BytesIO(base64.b64decode(data))) as sent:
        assert max(sent.size) == vlm_engine.VLM_MAX_IMAGE_SIDE


def test_missing_key_raises(face_image):
    with pytest.raises(VLMProviderError):
        VLMEngine().analyze("Gemini", face_image, "  ")


def test_normalize_handles_fenced_and_wrapped_json():
    text = '```json\n{"visible_observations": ["a"], "care_suggestions": "b"}\n```'
    assert strip_code_fence(text).startswith("{")
    result = normalize_vlm_json("Here you go: " + text, provider="X", model="m")
    assert result["visible_observations"] == ["a"]
    assert result["care_suggestions"] == ["b"]


def test_normalize_rejects_garbage_and_empty():
    with pytest.raises(VLMProviderError):
        normalize_vlm_json("not json", provider="X", model="m")
    with pytest.raises(VLMProviderError):
        normalize_vlm_json('{"visible_observations": []}', provider="X", model="m")
    with pytest.raises(VLMProviderError):
        normalize_vlm_json("[1, 2]", provider="X", model="m")


def test_compact_yolo_json_drops_paths():
    compact = compact_yolo_json({
        "image_path": "C:/secret/path.jpg",
        "model_path": "models/x.pt",
        "confidence_threshold": 0.1,
        "letterbox": {"original_width": 300, "original_height": 400},
        "findings": [{"confidence": 0.5, "box_original_xyxy": [1, 2, 3, 4], "box_640_xyxy": [0, 0, 0, 0]}],
        "summary": {"total_detections": 1},
    })
    assert "secret" not in json.dumps(compact)
    assert compact["findings"] == [{"confidence": 0.5, "box_xyxy": [1, 2, 3, 4]}]


def test_redact_and_router_model():
    assert redact_secret(f"oops {SECRET} and key=abc", SECRET) == "oops *** and key=***"
    assert build_hf_router_model("org/m") == "org/m:fastest"
    assert build_hf_router_model("org/m", "together") == "org/m:together"
    assert build_hf_router_model("org/m:novita", "together") == "org/m:novita"


def test_expired_key_and_no_credit_hints(face_image, fake_session):
    fake_session.post.return_value = _response(401, {"error": {"code": "expired_api_key"}})
    with pytest.raises(VLMProviderError, match="süresi dolmuş"):
        VLMEngine(VLMOptions(max_retries=0)).analyze("Groq", face_image, "gsk_test_key")
    fake_session.post.return_value = _response(402, {"error": "no remaining credits"})
    with pytest.raises(VLMProviderError, match="kredi"):
        VLMEngine(VLMOptions(max_retries=0)).analyze("HF", face_image, "hf_test_key")


def test_gemini_caps_thinking_budget(face_image, fake_session):
    fake_session.post.return_value = _response(200, _gemini_body({"visible_observations": ["a"], "care_suggestions": [], "disclaimer": ""}))
    VLMEngine().analyze("Gemini", face_image, SECRET)
    config = fake_session.post.call_args.kwargs["json"]["generationConfig"]
    # thinking tokens count against maxOutputTokens on 2.5 models; leave room for the JSON answer
    assert config["thinkingConfig"]["thinkingBudget"] < config["maxOutputTokens"] / 4


def _openai_body(text: str, status: str = "completed") -> dict:
    return {"status": status, "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "content": [{"type": "output_text", "text": text}]},
    ]}


def test_openai_uses_responses_api_with_bearer_key(face_image, fake_session):
    content = json.dumps({"visible_observations": ["x"], "care_suggestions": ["y"], "disclaimer": ""})
    fake_session.post.return_value = _response(200, _openai_body(content))
    result = VLMEngine(VLMOptions(openai_model="gpt-test")).analyze("OpenAI", face_image, "sk-test-key")
    call = fake_session.post.call_args
    payload = call.kwargs["json"]
    assert call.args[0] == vlm_engine.OPENAI_URL
    assert call.kwargs["headers"]["Authorization"] == "Bearer sk-test-key"
    assert "sk-test-key" not in json.dumps(payload)
    assert payload["model"] == "gpt-test" and payload["text"] == {"format": {"type": "json_object"}}
    parts = payload["input"][0]["content"]
    assert parts[0]["type"] == "input_text" and parts[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert result["provider"] == "OpenAI" and result["model"] == "gpt-test" and result["visible_observations"] == ["x"]


def test_openai_truncated_and_chat(face_image, fake_session):
    fake_session.post.return_value = _response(200, {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []})
    with pytest.raises(VLMProviderError) as error:
        VLMEngine().analyze("OpenAI", face_image, "sk-test-key")
    assert error.value.kind == "bad_output"
    fake_session.post.return_value = _response(200, _openai_body("Merhaba"))
    reply, model = VLMEngine(VLMOptions(openai_model="gpt-test")).chat("OpenAI", "sistem", [{"role": "user", "content": "selam"}], "sk-test-key")
    payload = fake_session.post.call_args.kwargs["json"]
    assert reply == "Merhaba" and model == "gpt-test"
    assert payload["instructions"] == "sistem" and payload["input"] == [{"role": "user", "content": "selam"}]
