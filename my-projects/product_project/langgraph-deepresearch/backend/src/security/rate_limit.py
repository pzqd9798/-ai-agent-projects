"""Simple in-memory sliding-window rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Optional


class RateLimiter:
    """Per-key sliding-window rate limiter."""

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: float = 60.0,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """Return True if the request is within the rate limit."""
        now = time.time()
        with self._lock:
            window = self._windows[key]
            # Evict expired timestamps
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.pop(0)
            if len(window) >= self.max_requests:
                return False
            window.append(now)
            return True

    def remaining(self, key: str) -> int:
        """How many requests remain in the current window."""
        now = time.time()
        with self._lock:
            window = self._windows[key]
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.pop(0)
            return max(0, self.max_requests - len(window))

    def reset(self, key: str) -> None:
        with self._lock:
            self._windows.pop(key, None)


# Singleton for API-level rate limiting
_global_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter(max_requests=60, window_seconds=60.0)
    return _global_limiter
