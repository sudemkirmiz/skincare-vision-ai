# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Cooldown registry (circuit breaker) shared by provider- and model-level fallback."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

# Seconds a provider/model is skipped after a failure of this kind.
COOLDOWN_SECONDS = {
    "auth": 30 * 60,
    "credits": 30 * 60,
    "quota": 60,
    "network": 30,
    "server": 30,
    "config": 10 * 60,
}
# Daily free-tier quotas report retry delays of many hours; honour them up to this cap.
MAX_RETRY_AFTER_SECONDS = 12 * 60 * 60


@dataclass
class _Cooldown:
    until: float
    kind: str


class ProviderHealth:
    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._cooldowns: dict[str, _Cooldown] = {}

    def mark_failure(self, name: str, kind: str, retry_after: float | None = None) -> None:
        seconds = COOLDOWN_SECONDS.get(kind)
        if seconds is None:  # bad_output / blocked are per-request, not a provider problem
            return
        if kind == "quota" and retry_after:
            seconds = max(seconds, min(retry_after, MAX_RETRY_AFTER_SECONDS))
        with self._lock:
            self._cooldowns[name] = _Cooldown(self._clock() + seconds, kind)

    def mark_success(self, name: str) -> None:
        with self._lock:
            self._cooldowns.pop(name, None)

    def blocked_reason(self, name: str) -> tuple[str, int] | None:
        """(kind, seconds left) while benched, else None."""
        with self._lock:
            cooldown = self._cooldowns.get(name)
            if cooldown is None:
                return None
            left = cooldown.until - self._clock()
            if left <= 0:
                del self._cooldowns[name]
                return None
            return cooldown.kind, int(left)

    def snapshot(self) -> dict[str, tuple[str, int]]:
        with self._lock:
            names = list(self._cooldowns)
        return {name: reason for name in names if (reason := self.blocked_reason(name))}
