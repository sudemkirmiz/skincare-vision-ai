from __future__ import annotations

import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_gemini_model_health(monkeypatch):
    """Model cooldowns are process-wide by design; tests must not leak them into each other."""
    import vlm_engine
    from health import ProviderHealth

    monkeypatch.setattr(vlm_engine, "GEMINI_MODEL_HEALTH", ProviderHealth())


class _NoNetworkSession:
    """Any test that forgets to mock HTTP fails loudly instead of calling a real (paid) API."""

    trust_env = False

    def post(self, *args, **kwargs):
        raise RuntimeError("Network access is disabled in tests; mock requests.Session.")

    def get(self, *args, **kwargs):
        raise RuntimeError("Network access is disabled in tests; mock requests.Session.")

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    import vlm_engine

    monkeypatch.setattr(vlm_engine.requests, "Session", _NoNetworkSession)
