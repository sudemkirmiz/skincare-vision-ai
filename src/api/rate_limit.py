"""Small process-local fixed-window limiter for expensive unauthenticated API work."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, window_seconds: float = 3600, clock=time.monotonic) -> None:
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}

    def take(self, subject: str, action: str, limit: int) -> tuple[bool, int]:
        now = self._clock()
        key = (subject, action)
        with self._lock:
            started, used = self._buckets.get(key, (now, 0))
            if now - started >= self.window_seconds:
                started, used = now, 0
            if used >= limit:
                retry_after = max(1, int(self.window_seconds - (now - started)))
                return False, retry_after
            self._buckets[key] = (started, used + 1)
            # Opportunistic cleanup keeps long-lived public processes bounded.
            if len(self._buckets) > 4096:
                self._buckets = {k: v for k, v in self._buckets.items() if now - v[0] < self.window_seconds}
            return True, 0
