"""
Adaptive rate limiter for controlling request frequency.
"""
import asyncio
import time
from utils.logger import logger

class AdaptiveRateLimiter:
    def __init__(self, initial_rate: float = 100.0, max_rate: float = 500.0, min_rate: float = 10.0):
        self.current_rate = initial_rate
        self.max_rate = max_rate
        self.min_rate = min_rate
        self._last_request = 0.0
        self._success_streak = 0
        self._failure_streak = 0
        self._lock = asyncio.Lock()
        self._rate_limit_cooldown_until = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            if now < self._rate_limit_cooldown_until:
                wait_time = self._rate_limit_cooldown_until - now
                logger.debug(f"Rate limiter cooling down for {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                now = time.monotonic()
            interval = 1.0 / self.current_rate
            elapsed = now - self._last_request
            if elapsed < interval: await asyncio.sleep(interval - elapsed)
            self._last_request = time.monotonic()

    async def report_success(self):
        self._success_streak += 1
        self._failure_streak = 0
        if self._success_streak >= 10:
            self.current_rate = min(self.current_rate * 1.1, self.max_rate)
            self._success_streak = 0
            logger.debug(f"Rate increased to {self.current_rate:.1f}/s")

    async def report_failure(self, rate_limited: bool = False):
        self._failure_streak += 1
        self._success_streak = 0
        if rate_limited:
            self.current_rate = max(self.current_rate * 0.5, self.min_rate)
            self._failure_streak = 0
            self._rate_limit_cooldown_until = time.monotonic() + 5.0
            logger.warning(f"Rate limit detected! Reducing rate to {self.current_rate:.1f}/s and cooling down 5s")
        elif self._failure_streak >= 3:
            self.current_rate = max(self.current_rate * 0.8, self.min_rate)
            self._failure_streak = 0
            logger.debug(f"Rate decreased to {self.current_rate:.1f}/s")

    async def wait_if_cooldown(self):
        remaining = self._rate_limit_cooldown_until - time.monotonic()
        if remaining > 0: await asyncio.sleep(remaining)

    @property
    def rate(self) -> float: return self.current_rate