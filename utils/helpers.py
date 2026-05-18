"""
Helper utilities for the scanner bot.
"""
import asyncio
import hashlib
import json
import time
from collections import deque
from functools import wraps
from typing import Any, Callable

def async_retry(max_retries: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions:
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (attempt + 1))
                    else:
                        raise
        return wrapper
    return decorator

def compute_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()

def format_time(seconds: float) -> str:
    if seconds < 0.1:
        return "0.1ث"
    elif seconds < 60:
        return f"{seconds:.1f}ث"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}د {s}ث"
    else:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return f"{h}س {m}د {s}ث"

def format_number(n: int) -> str:
    return f"{n:,}"

def json_serialize(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)

def json_deserialize(data: str) -> Any:
    return json.loads(data)

class RateTracker:
    def __init__(self, window: float = 1.0):
        self.window = window
        self.timestamps = deque()

    async def record(self):
        now = time.monotonic()
        self.timestamps.append(now)
        cutoff = now - self.window
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()

    @property
    def rate(self) -> float:
        now = time.monotonic()
        cutoff = now - self.window
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
        return len(self.timestamps) / self.window

    async def get_rate(self) -> float:
        return self.rate