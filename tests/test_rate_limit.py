from api.rate_limit import RateLimiter


def test_rate_limit_is_scoped_and_resets():
    now = [0.0]
    limiter = RateLimiter(window_seconds=10, clock=lambda: now[0])
    assert limiter.take("a", "analysis", 1) == (True, 0)
    allowed, retry_after = limiter.take("a", "analysis", 1)
    assert allowed is False and retry_after == 10
    assert limiter.take("b", "analysis", 1) == (True, 0)
    now[0] = 11
    assert limiter.take("a", "analysis", 1) == (True, 0)
