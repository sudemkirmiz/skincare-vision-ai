# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_defaults_are_local_and_hardened():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]

    assert app["ports"] == ["127.0.0.1:${APP_PORT:-8000}:8000"]
    assert app["read_only"] is True
    assert app["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in app["security_opt"]
    assert app["pids_limit"] <= 256
    assert "skincare_state:/app/state" in app["volumes"]
    assert app["environment"]["HISTORY_DB_PATH"] == "/app/state/history.db"
    assert app["healthcheck"]["retries"] >= 3


def test_production_compose_fails_closed():
    compose = yaml.safe_load((ROOT / "compose.production.yaml").read_text(encoding="utf-8"))
    environment = compose["services"]["app"]["environment"]

    assert environment["PUBLIC_DEPLOYMENT"] == "true"
    assert environment["ALLOW_USER_API_KEYS"] == "false"
    for key in ("APP_ACCESS_TOKEN", "ALLOWED_HOSTS", "CORS_ORIGINS"):
        assert ":?" in environment[key]


def test_runtime_image_is_minimal_and_non_root():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:22-bookworm-slim AS web" in dockerfile
    assert "FROM python:3.12-slim-bookworm AS runtime" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "COPY . ." not in dockerfile
    assert "/app/state" in dockerfile
    assert "--workers\", \"1" in dockerfile
    assert "LICENSE NOTICE TRADEMARKS.md THIRD_PARTY_NOTICES.md" in dockerfile
    assert "licenses/ ./licenses/" in dockerfile


def test_license_metadata_and_notices_are_consistent():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    expected = "AGPL-3.0-or-later"
    assert f'license = "{expected}"' in project
    assert package["license"] == expected
    assert package_lock["packages"][""]["license"] == expected
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "models/acne_like_spot.pt" in notices
    assert "models/face_landmarker.task" in notices
    assert (ROOT / "licenses/APACHE-2.0.txt").is_file()
    assert (ROOT / "licenses/FRAUNCES-OFL-1.1.txt").is_file()
    assert (ROOT / "licenses/INTER-OFL-1.1.txt").is_file()
