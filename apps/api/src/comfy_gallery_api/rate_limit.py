from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable


class LoginRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_blocked(self, key: str) -> bool:
        async with self._lock:
            failures = self._current_failures(key)
            return len(failures) >= self.limit

    async def record_failure(self, key: str) -> None:
        async with self._lock:
            failures = self._current_failures(key)
            failures.append(self.clock())

    async def clear(self, key: str) -> None:
        async with self._lock:
            self._failures.pop(key, None)

    def _current_failures(self, key: str) -> deque[float]:
        failures = self._failures[key]
        cutoff = self.clock() - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
            failures = self._failures[key]
        return failures
