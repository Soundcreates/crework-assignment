from __future__ import annotations

import asyncio
import time
from collections import deque


class TokenBucketLimiter:
    """Process-wide limiter: at most `rate_per_minute` acquisitions per rolling window."""

    def __init__(self, rate_per_minute: int = 15, window_seconds: float = 60.0):
        self.rate_per_minute = max(1, int(rate_per_minute))
        self.window_seconds = window_seconds
        self._times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        waited = 0.0
        async with self._lock:
            while True:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                while self._times and self._times[0] < cutoff:
                    self._times.popleft()
                if len(self._times) < self.rate_per_minute:
                    self._times.append(now)
                    return waited
                sleep_for = max(0.01, self.window_seconds - (now - self._times[0]) + 0.01)
                waited += sleep_for
                await asyncio.sleep(sleep_for)


_limiters: dict[int, TokenBucketLimiter] = {}
_limiters_lock = asyncio.Lock()


async def get_shared_limiter(rate_per_minute: int) -> TokenBucketLimiter:
    key = max(1, int(rate_per_minute))
    async with _limiters_lock:
        limiter = _limiters.get(key)
        if limiter is None:
            limiter = TokenBucketLimiter(key)
            _limiters[key] = limiter
        return limiter


def parse_rate_limit_wait(headers: dict[str, str] | None, default: float = 2.0) -> float:
    """Honor X-RateLimit-Reset (unix seconds or delta) and Retry-After."""
    if not headers:
        return default
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    retry_after = lowered.get("retry-after")
    if retry_after:
        try:
            return max(default, float(retry_after))
        except ValueError:
            pass
    reset = lowered.get("x-ratelimit-reset")
    if reset:
        try:
            value = float(reset)
        except ValueError:
            return default
        now = time.time()
        if value > now:
            return max(default, value - now)
        if value > 120:
            # likely a unix timestamp in the past
            return default
        return max(default, value)
    return default


def is_rate_limit_error(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status == 429:
        return True
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def rate_limit_headers_from_exc(exc: BaseException) -> dict[str, str]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return {}
    try:
        return {str(k): str(v) for k, v in headers.items()}
    except Exception:  # noqa: BLE001
        return {}
