from comfy_gallery_api.rate_limit import LoginRateLimiter


async def test_login_rate_limit_expires_and_success_can_clear() -> None:
    now = 100.0
    limiter = LoginRateLimiter(limit=2, window_seconds=30, clock=lambda: now)
    assert not await limiter.is_blocked("client")
    await limiter.record_failure("client")
    await limiter.record_failure("client")
    assert await limiter.is_blocked("client")

    await limiter.clear("client")
    assert not await limiter.is_blocked("client")

    await limiter.record_failure("client")
    await limiter.record_failure("client")
    now = 131.0
    assert not await limiter.is_blocked("client")
