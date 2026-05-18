"""
Advanced proxy rotator with automatic discovery and testing.
"""
import asyncio
import aiohttp
import random
import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from utils.logger import logger
from config import ADV_CONFIG

@dataclass
class Proxy:
    host: str
    port: int
    protocol: str
    username: Optional[str] = None
    password: Optional[str] = None
    latency: float = float('inf')
    last_used: float = 0
    fail_count: int = 0
    success_count: int = 0
    rate_limit_count: int = 0
    country: Optional[str] = None
    is_alive: bool = False

    @property
    def url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"

    @property
    def reliability(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.5

class ProxyDiscoveryEngine:
    PROXY_SOURCES = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    ]

    async def discover_proxies(self) -> List[Proxy]:
        all_proxies = []
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [self._fetch_proxy_source(session, url) for url in self.PROXY_SOURCES]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, list): all_proxies.extend(result)
        except Exception as e: logger.warning(f"Proxy discovery failed: {e}")
        logger.info(f"Discovered {len(all_proxies)} proxies")
        return all_proxies

    async def _fetch_proxy_source(self, session: aiohttp.ClientSession, url: str) -> List[Proxy]:
        proxies = []
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    text = await response.text()
                    proxies = self._parse_proxy_list(text)
        except Exception as e: logger.debug(f"Failed to fetch from {url}: {e}")
        return proxies

    def _parse_proxy_list(self, text: str) -> List[Proxy]:
        proxies = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split(':')
            if len(parts) == 2:
                host, port_str = parts
                try: proxies.append(Proxy(host=host, port=int(port_str), protocol="http"))
                except ValueError: pass
        return proxies

class ProxyRotator:
    def __init__(self):
        self.discovery = ProxyDiscoveryEngine()
        self.proxies: List[Proxy] = []
        self.active_proxies: List[Proxy] = []
        self.blacklisted_proxies: Set[str] = set()
        self._lock = asyncio.Lock()
        self.current_index = 0
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def initialize(self):
        if not ADV_CONFIG.use_proxies:
            logger.info("Proxy usage disabled")
            return
        if ADV_CONFIG.proxy_list_file: await self._load_from_file()
        discovered = await self.discovery.discover_proxies()
        self.proxies.extend(discovered)
        self._remove_duplicates()
        await self._validate_proxies()
        logger.info(f"Proxy rotator initialized with {len(self.active_proxies)} active proxies")

    async def get_proxy(self) -> Optional[Proxy]:
        async with self._lock:
            if not self.active_proxies: return None
            ranked = sorted(self.active_proxies, key=lambda p: (p.reliability, -p.latency if p.latency != float('inf') else 0), reverse=True)
            candidates = ranked[:max(1, len(ranked) // 3)]
            proxy = random.choice(candidates)
            proxy.last_used = time.time()
            return proxy

    async def report_result(self, proxy: Proxy, success: bool, rate_limited: bool = False):
        async with self._lock:
            if success:
                proxy.success_count += 1; self.successful_requests += 1; proxy.rate_limit_count = 0
            else:
                proxy.fail_count += 1; self.failed_requests += 1
                if rate_limited: proxy.rate_limit_count += 1
            self.total_requests += 1
            if proxy.fail_count > ADV_CONFIG.max_failed_proxies or proxy.rate_limit_count >= 3:
                if proxy in self.active_proxies:
                    self.active_proxies.remove(proxy)
                    self.blacklisted_proxies.add(f"{proxy.host}:{proxy.port}")
                    logger.warning(f"Proxy removed: {proxy.url} (fails={proxy.fail_count}, rate_limits={proxy.rate_limit_count})")

    async def _load_from_file(self):
        try:
            import aiofiles
            async with aiofiles.open(ADV_CONFIG.proxy_list_file, 'r') as f:
                content = await f.read()
                proxies = self.discovery._parse_proxy_list(content)
                self.proxies.extend(proxies)
                logger.info(f"Loaded {len(proxies)} proxies from file")
        except Exception as e: logger.warning(f"Failed to load proxies from file: {e}")

    async def _validate_proxies(self):
        if not self.proxies: return
        logger.info(f"Testing {len(self.proxies)} proxies...")
        test_proxies = self.proxies[:100]
        semaphore = asyncio.Semaphore(50)
        async def test_with_semaphore(proxy: Proxy) -> bool:
            async with semaphore:
                async with aiohttp.ClientSession() as session:
                    return await self._test_proxy(session, proxy)
        tasks = [test_with_semaphore(proxy) for proxy in test_proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for proxy, is_alive in zip(test_proxies, results):
            if isinstance(is_alive, bool) and is_alive: self.active_proxies.append(proxy)
        logger.info(f"Active proxies: {len(self.active_proxies)}/{len(test_proxies)}")

    async def _test_proxy(self, session: aiohttp.ClientSession, proxy: Proxy) -> bool:
        start_time = time.monotonic()
        try:
            async with session.get("https://t.me", proxy=proxy.url, timeout=aiohttp.ClientTimeout(total=ADV_CONFIG.proxy_timeout), ssl=False) as response:
                proxy.latency = time.monotonic() - start_time
                if response.status >= 500:
                    proxy.is_alive = False; return False
                body = await response.text()
                body_l = body.lower()
                if "telegram" in body_l or "tgme" in body_l:
                    proxy.is_alive = True; return True
                proxy.is_alive = False; return False
        except Exception:
            proxy.is_alive = False; return False

    def _remove_duplicates(self):
        seen = set()
        unique = []
        for proxy in self.proxies:
            key = f"{proxy.host}:{proxy.port}:{proxy.protocol}"
            if key not in seen:
                seen.add(key); unique.append(proxy)
        self.proxies = unique

    async def close(self):
        self.proxies.clear()
        self.active_proxies.clear()