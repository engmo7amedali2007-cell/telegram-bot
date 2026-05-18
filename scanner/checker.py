import asyncio
import random
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from curl_cffi.requests import AsyncSession
from utils.logger import logger
from utils.constants import UsernameStatus, Confidence
from utils.reserved_usernames import is_reserved
from config import ADV_CONFIG
from scanner.proxy_rotator import ProxyRotator
from scanner.rate_limiter import AdaptiveRateLimiter

@dataclass
class CheckResult:
    username: str
    status: UsernameStatus
    confidence: float
    method: str
    response_time: float
    http_status: int
    redirect_url: Optional[str] = None
    rate_limited: bool = False

class AdvancedUsernameChecker:
    FRAGMENT_API = "https://fragment.com/username/check"

    def __init__(self):
        self.session: Optional[AsyncSession] = None
        self.total_checks = 0
        self.successful_checks = 0
        self.failed_checks = 0
        self.rate_limit_hits = 0
        self._warmed_up = False
        self.response_cache: Dict[str, Tuple[float, CheckResult]] = {}
        self.proxy_rotator = ProxyRotator()
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=ADV_CONFIG.rate_limit,
            max_rate=ADV_CONFIG.rate_limit * 2,
            min_rate=5
        )

    async def initialize(self):
        if ADV_CONFIG.use_proxies:
            await self.proxy_rotator.initialize()
        self.session = AsyncSession(impersonate="chrome120")

    async def close(self):
        if self.session:
            await self.session.close()

    async def warm_up(self):
        try:
            resp = await self.session.get(
                "https://t.me/telegram",
                headers=self._get_headers(),
                allow_redirects=True,
            )
            await resp.atext()
            self._warmed_up = True
            logger.info("Checker warmed up")
        except Exception as e:
            logger.warning(f"Warm-up failed: {e}")

    async def check_username(self, username: str) -> CheckResult:
        self.total_checks += 1
        if is_reserved(username):
            return CheckResult(username=username, status=UsernameStatus.RESERVED, confidence=Confidence.HIGH.value, method="blocklist", response_time=0, http_status=0)
        if len(username) < 5 or username.isdigit():
            return CheckResult(username=username, status=UsernameStatus.INVALID, confidence=Confidence.HIGH.value, method="validation", response_time=0, http_status=0)
        if username in self.response_cache:
            ts, cached = self.response_cache[username]
            if cached.status != UsernameStatus.UNKNOWN and time.time() - ts < ADV_CONFIG.cache_ttl:
                return cached
        if not self._warmed_up:
            await self.warm_up()

        fragment_result = await self._check_fragment_api(username)

        if fragment_result.status == UsernameStatus.AVAILABLE:
            tme_result = await self._check_t_me(username)
            if tme_result.status == UsernameStatus.TAKEN:
                logger.info(f"@{username}: Fragment=AVAILABLE but t.me=TAKEN → marking TAKEN")
                result = tme_result
            elif tme_result.status == UsernameStatus.UNKNOWN:
                logger.info(f"@{username}: Fragment=AVAILABLE but t.me=UNKNOWN → marking UNKNOWN")
                result = CheckResult(username=username, status=UsernameStatus.UNKNOWN, confidence=0, method="fragment_api_unconfirmed", response_time=0, http_status=0)
            else:
                result = tme_result
        elif fragment_result.status in (UsernameStatus.TAKEN, UsernameStatus.RESERVED, UsernameStatus.INVALID):
            logger.debug(f"@{username}: Fragment={fragment_result.status.name} → falling back to t.me")
            tme_result = await self._check_t_me(username)
            if tme_result.status == UsernameStatus.AVAILABLE: result = tme_result
            else: result = fragment_result
        else:
            logger.debug(f"@{username}: Fragment failed → falling back to t.me")
            result = await self._check_t_me(username)

        if result.status != UsernameStatus.UNKNOWN:
            self.response_cache[username] = (time.time(), result)
            self.successful_checks += 1
        else:
            self.failed_checks += 1
        return result

    async def _check_fragment_api(self, username: str) -> CheckResult:
        await self.rate_limiter.acquire()
        start = time.monotonic()
        params = {"username": username}
        try:
            resp = await self.session.get(self.FRAGMENT_API, params=params, headers=self._get_headers(json_mode=True), allow_redirects=True)
            elapsed = time.monotonic() - start
            if self._is_rate_limited(resp.status_code, ""):
                self.rate_limit_hits += 1
                logger.warning(f"[Fragment] @{username} → RATE-LIMITED")
                return CheckResult(username=username, status=UsernameStatus.UNKNOWN, confidence=0, method="fragment_ratelimit", response_time=elapsed, http_status=resp.status_code, rate_limited=True)
            if resp.status_code != 200:
                return self._unknown(username, f"fragment_http_{resp.status_code}", elapsed)
            try:
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = resp.json()
                else:
                    return self._unknown(username, "fragment_not_json", elapsed)
            except Exception:
                return self._unknown(username, "fragment_parse_error", elapsed)

            frag_status = (data.get("status") or "").lower()
            status = self._parse_fragment_status(frag_status)
            logger.debug(f"[Fragment] @{username} → {status.name} ({frag_status!r})")
            return CheckResult(username=username, status=status, confidence=Confidence.HIGH.value if status != UsernameStatus.UNKNOWN else 0, method="fragment_api", response_time=elapsed, http_status=resp.status_code)
        except Exception as e:
            logger.debug(f"[Fragment] @{username} → error: {e}")
            return self._unknown(username, "fragment_error", time.monotonic() - start)

    def _parse_fragment_status(self, frag_status: str) -> UsernameStatus:
        mapping = {"available": UsernameStatus.AVAILABLE, "taken": UsernameStatus.TAKEN, "sold": UsernameStatus.TAKEN, "reserved": UsernameStatus.RESERVED, "invalid": UsernameStatus.INVALID, "": UsernameStatus.UNKNOWN}
        return mapping.get(frag_status, UsernameStatus.UNKNOWN)

    async def _check_t_me(self, username: str) -> CheckResult:
        await self.rate_limiter.acquire()
        proxy_url = None
        if ADV_CONFIG.use_proxies:
            proxy = await self.proxy_rotator.get_proxy()
            if proxy: proxy_url = proxy.url
            
        start = time.monotonic()
        url = f"https://t.me/{username}"
        try:
            resp = await self.session.get(url, headers=self._get_headers(), allow_redirects=True, proxy=proxy_url)
            elapsed = time.monotonic() - start
            final_url = str(resp.url)
            body = await resp.atext()
            body_l = body.lower()

            if "t.me" not in final_url:
                if "telegram.org" in final_url:
                    logger.debug(f"[t.me] @{username} → redirected to telegram.org, analyzing body")
                    status = self._analyze_telegram_org_body(body_l, username)
                    if status == UsernameStatus.AVAILABLE:
                        logger.info(f"[t.me] @{username} → AVAILABLE (from telegram.org body)")
                        return CheckResult(username=username, status=UsernameStatus.AVAILABLE, confidence=Confidence.MEDIUM.value, method="t.me_redirect_analyzed", response_time=elapsed, http_status=resp.status_code, redirect_url=final_url)
                    else:
                        return CheckResult(username=username, status=UsernameStatus.UNKNOWN, confidence=0, method="t.me_redirect_unclear", response_time=elapsed, http_status=resp.status_code, redirect_url=final_url)
                else:
                    logger.debug(f"[t.me] @{username} → INVALID (redirected to {final_url[:50]})")
                    return CheckResult(username=username, status=UsernameStatus.INVALID, confidence=Confidence.HIGH.value, method="t.me_redirect", response_time=elapsed, http_status=resp.status_code, redirect_url=final_url)

            if self._is_rate_limited(resp.status_code, body_l):
                self.rate_limit_hits += 1
                logger.warning(f"[t.me] @{username} → RATE-LIMITED")
                return CheckResult(username=username, status=UsernameStatus.UNKNOWN, confidence=0, method="t.me_ratelimit", response_time=elapsed, http_status=resp.status_code, rate_limited=True)

            status = self._analyze_t_me_body(body_l, username)
            if proxy and proxy_url:
                await self.proxy_rotator.report_result(proxy, success=(status != UsernameStatus.UNKNOWN))
            if status != UsernameStatus.UNKNOWN:
                await self.rate_limiter.report_success()
            else:
                await self.rate_limiter.report_failure()

            logger.debug(f"[t.me] @{username} → {status.name}")
            return CheckResult(username=username, status=status, confidence=Confidence.HIGH.value if status != UsernameStatus.UNKNOWN else 0, method="t.me", response_time=elapsed, http_status=resp.status_code)
        except Exception as e:
            logger.debug(f"[t.me] @{username} → error: {e}")
            return self._unknown(username, "error", time.monotonic() - start)

    def _is_rate_limited(self, status: int, body_l: str) -> bool:
        if status in (429, 503, 403): return True
        if not body_l: return False
        markers = ["just a moment", "cf-ray", "checking your browser", "enable javascript and cookies", "ray id", "ddos protection", "please wait…"]
        return any(m in body_l for m in markers)

    def _analyze_t_me_body(self, body_l: str, username: str = "") -> UsernameStatus:
        if "if you have telegram, you can contact" in body_l:
            if "tgme_action_button_new" not in body_l and "tgme_page_photo" not in body_l and "tgme_page_title" not in body_l:
                return UsernameStatus.AVAILABLE
        if "tgme_page_photo" in body_l or "tgme_page_title" in body_l or 'property="og:image"' in body_l:
            if "telegram_logo" not in body_l:
                return UsernameStatus.TAKEN
        return UsernameStatus.UNKNOWN

    def _analyze_telegram_org_body(self, body_l: str, username: str) -> UsernameStatus:
        available_phrases = ["you can contact", "available", "choose a username", "start a channel", "create a group", "get started", "you will be able to contact"]
        if any(phrase in body_l for phrase in available_phrases): return UsernameStatus.AVAILABLE
        return UsernameStatus.UNKNOWN

    def _get_headers(self, json_mode: bool = False) -> Dict[str, str]:
        pool = ADV_CONFIG.header_rotation_pool
        if json_mode:
            return {"User-Agent": random.choice(ADV_CONFIG.user_agents), "Accept": "application/json, text/plain, */*", "Accept-Language": random.choice(pool["accept_language"]), "Accept-Encoding": "gzip, deflate, br", "Connection": "keep-alive", "Referer": "https://fragment.com/", "Origin": "https://fragment.com"}
        return {"User-Agent": random.choice(ADV_CONFIG.user_agents), "Accept": random.choice(pool["accept"]), "Accept-Language": random.choice(pool["accept_language"]), "Accept-Encoding": random.choice(pool["accept_encoding"]), "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1"}

    def _unknown(self, username: str, method: str, elapsed: float) -> CheckResult:
        return CheckResult(username=username, status=UsernameStatus.UNKNOWN, confidence=0, method=method, response_time=elapsed, http_status=0)