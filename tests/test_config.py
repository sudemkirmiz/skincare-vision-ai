# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
import os

from config import get_settings, load_env_file


def test_env_loader_handles_quotes_comments_and_precedence(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('A_KEY="quoted # not comment"\nB_KEY=value # comment\n# skip\nC_KEY=file\n', encoding="utf-8")
    for key in ("A_KEY", "B_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("C_KEY", "real-env")
    load_env_file(env)

    assert os.environ["A_KEY"] == "quoted # not comment"
    assert os.environ["B_KEY"] == "value"
    assert os.environ["C_KEY"] == "real-env"
    monkeypatch.delenv("A_KEY")
    monkeypatch.delenv("B_KEY")


def test_settings_fall_back_on_bad_values(monkeypatch):
    monkeypatch.setenv("YOLO_CONFIDENCE", "not-a-number")
    monkeypatch.setenv("ALLOW_USER_API_KEYS", "false")
    settings = get_settings()
    assert settings.yolo_confidence == 0.10
    assert settings.allow_user_api_keys is False
    assert settings.yolo_model_path.is_absolute()
    assert settings.analysis_rate_limit > 0 and settings.label_rate_limit > 0
    assert settings.capture_rate_limit > 0
    assert settings.max_request_body_mb >= 2
