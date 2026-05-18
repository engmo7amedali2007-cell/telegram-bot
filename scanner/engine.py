"""
Scanning engine — producer-consumer pattern, cookie-safe, accurate.
"""
import asyncio
import time
import random
import aiofiles
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from utils.logger import logger
from utils.constants import ScanStatus, UsernameStatus
from utils.helpers import RateTracker, format_time
from config import ADV_CONFIG
from .checker import AdvancedUsernameChecker, CheckResult
from .proxy_rotator import ProxyRotator
from generators.username_generator import UsernameGenerator

@dataclass
class ScanProgress:
    total_usernames: int
    checked: int = 0
    available: int = 0
    taken: int = 0
    reserved: int = 0
    invalid: int = 0
    errors: int = 0
    retries: int = 0
    rate_limit_hits: int = 0
    start_time: float = 0
    elapsed_time: float = 0
    speed: float = 0
    estimated_time_remaining: float = 0

    @property
    def completion_percentage(self) -> float:
        if self.total_usernames == 0: return 0
        return min(100.0, (self.checked / self.total_usernames) * 100)

    @property
    def success_rate(self) -> float:
        definitive = self.available + self.taken + self.invalid
        return (definitive / max(self.checked, 1)) * 100

class ScanManager:
    def __init__(self):
        self.scans: Dict[str, "ScanOperation"] = {}
        self.checker = AdvancedUsernameChecker()
        self.proxy_rotator = ProxyRotator()
        self._lock = asyncio.Lock()

    async def initialize(self):
        await self.checker.initialize()
        if ADV_CONFIG.use_proxies:
            await self.proxy_rotator.initialize()

    async def create_scan(self, scan_id: str, pattern: str, user_id: int, save_path: str) -> "ScanOperation":
        op = ScanOperation(scan_id=scan_id, pattern=pattern, user_id=user_id, save_path=save_path, checker=self.checker)
        async with self._lock: self.scans[scan_id] = op
        return op

    async def get_scan(self, scan_id: str) -> Optional["ScanOperation"]:
        async with self._lock: return self.scans.get(scan_id)

    async def list_scans(self, user_id: int) -> List["ScanOperation"]:
        async with self._lock: return [s for s in self.scans.values() if s.user_id == user_id]

    async def stop_all_scans(self):
        async with self._lock:
            for scan in self.scans.values(): await scan.stop()

    async def close(self):
        await self.stop_all_scans()
        await self.checker.close()

class ScanOperation:
    def __init__(self, scan_id: str, pattern: str, user_id: int, save_path: str, checker: AdvancedUsernameChecker):
        self.scan_id = scan_id
        self.pattern = pattern
        self.user_id = user_id
        self.save_path = save_path
        self.checker = checker
        self.status = ScanStatus.IDLE
        self.progress = ScanProgress(total_usernames=0)
        self.generator = UsernameGenerator(pattern)
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stop_flag = False
        self.available_usernames: Set[str] = set()
        self.rate_tracker = RateTracker()
        self._save_task: Optional[asyncio.Task] = None
        self._main_task: Optional[asyncio.Task] = None
        self._unknown_queue: List[str] = []
        self._retry_counts: Dict[str, int] = {}
        self._max_retries_per_username = 2

    async def start(self) -> int:
        self.status = ScanStatus.RUNNING
        self.progress.start_time = time.monotonic()
        self.progress.total_usernames = self.generator.raw_combinations_count
        workers = self._optimal_workers()
        logger.info(f"Scan started: {self.scan_id} | Pattern: {self.pattern} | Total: {self.progress.total_usernames:,} | Workers: {workers}")
        self._save_task = asyncio.create_task(self._auto_save_loop())
        self._main_task = asyncio.create_task(self._run(workers))
        return self.progress.total_usernames

    async def pause(self):
        if self.status == ScanStatus.RUNNING:
            self.status = ScanStatus.PAUSED
            self._pause_event.clear()
            logger.info(f"Scan paused: {self.scan_id}")

    async def resume(self):
        if self.status == ScanStatus.PAUSED:
            self.status = ScanStatus.RUNNING
            self._pause_event.set()
            logger.info(f"Scan resumed: {self.scan_id}")

    async def stop(self):
        if self.status in (ScanStatus.RUNNING, ScanStatus.PAUSED):
            self.status = ScanStatus.STOPPING
            self._stop_flag = True
            self._pause_event.set()
            if self._main_task: self._main_task.cancel()
            if self._save_task: self._save_task.cancel()
            await self._final_save()
            self.status = ScanStatus.STOPPED
            logger.info(f"Scan stopped: {self.scan_id}")

    async def _run(self, num_workers: int):
        try:
            await self.checker.warm_up()
            queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=num_workers * 4)
            producer = asyncio.create_task(self._producer(queue, num_workers))
            workers = [asyncio.create_task(self._worker(queue, worker_id=i)) for i in range(num_workers)]
            await asyncio.gather(producer, *workers)
            if self._unknown_queue and not self._stop_flag:
                await self._retry_pass(num_workers)
            if not self._stop_flag:
                self.status = ScanStatus.COMPLETED
                await self._final_save()
        except asyncio.CancelledError: pass
        except Exception as e:
            logger.error(f"Scan error {self.scan_id}: {e}", exc_info=True)
            self.status = ScanStatus.ERROR

    async def _producer(self, queue: asyncio.Queue, num_workers: int):
        try:
            async for chunk in self.generator.generate_chunks(1):
                if self._stop_flag: break
                username = chunk[0]
                await queue.put(username)
        finally:
            for _ in range(num_workers): await queue.put(None)

    async def _worker(self, queue: asyncio.Queue, worker_id: int):
        while True:
            username = await queue.get()
            try: 
                if username is None or self._stop_flag: return
                await self._pause_event.wait()
                if self._stop_flag: return
                await asyncio.sleep(random.uniform(ADV_CONFIG.request_delay_min, ADV_CONFIG.request_delay_max))
                result = await self.checker.check_username(username)
                await self.rate_tracker.record()
                await self._record(result)
            finally: queue.task_done()

    async def _retry_pass(self, num_workers: int):
        hits = self.progress.rate_limit_hits
        cooldown = min(ADV_CONFIG.rate_limit_backoff_initial * (ADV_CONFIG.rate_limit_backoff_multiplier ** hits), ADV_CONFIG.rate_limit_backoff_max) if hits > 0 else ADV_CONFIG.retry_cooldown

        usernames_to_retry = []
        for username in list(self._unknown_queue):
            retries = self._retry_counts.get(username, 0)
            if retries < self._max_retries_per_username:
                usernames_to_retry.append(username)
            else:
                self._write_to_failed_file(username)
                self._unknown_queue.remove(username)

        if not usernames_to_retry: return
        logger.info(f"Retry pass: {len(usernames_to_retry)} UNKNOWN usernames (rate-limit hits={hits}, cooldown={cooldown:.1f}s)")
        await asyncio.sleep(cooldown)
        await self.checker.warm_up()

        queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=num_workers * 4)
        async def retry_producer():
            for u in usernames_to_retry:
                if self._stop_flag: break
                await queue.put(u)
            for _ in range(num_workers): await queue.put(None)

        async def retry_worker(wid: int):
            while True:
                username = await queue.get()
                try:
                    if username is None or self._stop_flag: return
                    await asyncio.sleep(random.uniform(ADV_CONFIG.request_delay_min * 2, ADV_CONFIG.request_delay_max * 2))
                    result = await self.checker.check_username(username)
                    self.progress.retries += 1
                    self._retry_counts[username] = self._retry_counts.get(username, 0) + 1

                    if result.status != UsernameStatus.UNKNOWN:
                        self.progress.errors = max(0, self.progress.errors - 1)
                        await self._record(result)
                    else:
                        if self._retry_counts[username] >= self._max_retries_per_username:
                            self._write_to_failed_file(username)
                            if username in self._unknown_queue: self._unknown_queue.remove(username)
                        logger.debug(f"Retry still UNKNOWN: @{username}")
                finally: queue.task_done()

        producer = asyncio.create_task(retry_producer())
        workers = [asyncio.create_task(retry_worker(i)) for i in range(num_workers)]
        await asyncio.gather(producer, *workers)

    async def _record(self, result: CheckResult):
        self.progress.checked += 1
        self.progress.elapsed_time = time.monotonic() - self.progress.start_time
        self.progress.speed = await self.rate_tracker.get_rate()
        remaining = self.progress.total_usernames - self.progress.checked
        if self.progress.speed > 0: self.progress.estimated_time_remaining = remaining / self.progress.speed
        if result.rate_limited: self.progress.rate_limit_hits += 1

        if result.status == UsernameStatus.AVAILABLE:
            self.progress.available += 1; self.available_usernames.add(result.username)
        elif result.status == UsernameStatus.TAKEN: self.progress.taken += 1
        elif result.status == UsernameStatus.RESERVED: self.progress.reserved += 1
        elif result.status == UsernameStatus.INVALID: self.progress.invalid += 1
        elif result.status == UsernameStatus.UNKNOWN:
            self.progress.errors += 1; self._unknown_queue.append(result.username)

    def _write_to_failed_file(self, username: str):
        failed_file = self.save_path.replace(".txt", "_failed.txt")
        try:
            with open(failed_file, "a", encoding="utf-8") as f: f.write(f"{username}\n")
        except Exception as e: logger.error(f"Failed to write {username} to failed file: {e}")

    async def _auto_save_loop(self):
        try:
            while not self._stop_flag:
                await asyncio.sleep(5)
                await self._save_results()
        except asyncio.CancelledError: pass

    async def _save_results(self):
        if not self.available_usernames: return 
        try:
            async with aiofiles.open(self.save_path, "w", encoding="utf-8") as f:
                for username in sorted(self.available_usernames): await f.write(f"{username}\n")
        except Exception as e: logger.error(f"Save error: {e}")

    async def _final_save(self):
        await self._save_results()
        logger.info(f"Final save: {self.save_path}")

    def _optimal_workers(self) -> int:
        total = self.progress.total_usernames
        if total <= 100: return min(2, ADV_CONFIG.max_workers)
        elif total <= 1_000: return min(3, ADV_CONFIG.max_workers)
        else: return min(ADV_CONFIG.max_workers, 5)

    def get_progress_message(self) -> str:
        p = self.progress
        pct = p.completion_percentage
        elapsed = format_time(p.elapsed_time) if p.elapsed_time else "0ث"
        eta = format_time(p.estimated_time_remaining) if p.estimated_time_remaining > 0 else "?"
        speed = f"{p.speed:.1f}"
        bar_filled = int(pct / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        status_text = self.status.value if hasattr(self.status, "value") else str(self.status)
        reserved_line = f"🔒 محجوز: {p.reserved:,}\n" if p.reserved > 0 else ""
        error_line = f"⚠️ أخطاء: {p.errors:,}\n" if p.errors > 0 else ""
        retry_line = f"🔁 إعادة محاولة: {p.retries:,}\n" if p.retries > 0 else ""
        rate_line = f"🚦 تهييج: {p.rate_limit_hits:,}\n" if p.rate_limit_hits > 0 else ""

        return (f"🔍 **فحص اليوزرات**\n\n📝 النمط: `{self.pattern}`\n📊 الحالة: {status_text}\n\n`[{bar}]` {pct:.1f}%\n\n✅ متاح: **{p.available:,}**\n❌ مستخدم: {p.taken:,}\n{reserved_line}⚠️ غير صالح: {p.invalid:,}\n{error_line}{retry_line}{rate_line}🔢 تم الفحص: {p.checked:,}/{p.total_usernames:,}\n\n⚡ السرعة: {speed}/s\n⏱️ الوقت: {elapsed} | المتبقي: {eta}")