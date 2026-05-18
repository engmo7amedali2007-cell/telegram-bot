"""
Advanced configuration with stealth and bypass techniques.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AdvancedConfig:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_id: int = field(default_factory=lambda: int(os.getenv("ADMIN_ID", "0")))
    use_proxies: bool = field(default_factory=lambda: os.getenv("USE_PROXIES", "false").lower() == "true")
    proxy_list_file: str = field(default_factory=lambda: os.getenv("PROXY_LIST", "proxies.txt"))
    proxy_rotation_strategy: str = "round_robin"
    proxy_timeout: float = 3.0
    proxy_check_interval: int = 60
    max_failed_proxies: int = 10
    proxy_types: List[str] = field(default_factory=lambda: ["socks5", "socks4", "http", "https"])
    enable_spoofing: bool = field(default_factory=lambda: os.getenv("ENABLE_SPOOFING", "true").lower() == "true")
    tls_fingerprints: List[Dict] = field(default_factory=lambda: [
        {"client_hello": "chrome_120", "signature_algorithms": "ecdsa_secp256r1_sha256"},
        {"client_hello": "firefox_121", "signature_algorithms": "rsa_pss_rsae_sha256"},
        {"client_hello": "safari_17", "signature_algorithms": "ecdsa_secp384r1_sha384"},
    ])
    http2_settings: Dict = field(default_factory=lambda: {
        "header_table_size": 65536, "initial_window_size": 6291456,
        "max_concurrent_streams": 100, "max_header_list_size": 262144,
    })
    tcp_params: Dict = field(default_factory=lambda: {"window_size": 65535, "ttl": 64, "mss": 1460, "wscale": 7})
    fragment_requests: bool = True
    fragment_size_min: int = 100
    fragment_size_max: int = 500
    fragment_delay: float = 0.01
    fragment_strategy: str = "random"
    use_custom_dns: bool = field(default_factory=lambda: os.getenv("USE_CUSTOM_DNS", "true").lower() == "true")
    dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220"])
    dns_query_timeout: float = 2.0
    dns_cache_size: int = 100000
    bypass_cloudflare: bool = field(default_factory=lambda: os.getenv("BYPASS_CLOUDFLARE", "true").lower() == "true")
    cloudflare_bypass_methods: List[str] = field(default_factory=lambda: ["js_challenge", "turnstile", "webp_cookie", "header_spoofing"])
    header_rotation_pool: Dict = field(default_factory=lambda: {
        "accept": ["text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "application/json, text/plain, */*"],
        "accept_language": ["en-US,en;q=0.9", "en-GB,en;q=0.8", "ar-SA,ar;q=0.9,en;q=0.8"],
        "accept_encoding": ["gzip, deflate, br", "gzip, deflate, br, zstd", "gzip, deflate"],
        "sec_ch_ua": ['"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"', '"Not_A Brand";v="8", "Chromium";v="119", "Google Chrome";v="119"'],
        "sec_ch_ua_platform": ['"Windows"', '"macOS"', '"Linux"', '"Android"'],
        "sec_ch_ua_mobile": ['?0', '?1'],
    })
    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Android 14; Mobile; rv:121.0) Gecko/121.0 Firefox/121.0",
    ])
    enable_timing_attacks: bool = True
    response_time_thresholds: Dict = field(default_factory=lambda: {"available": 0.3, "taken": 1.0, "rate_limited": 0.1})
    rate_limit_bypass_methods: List[str] = field(default_factory=lambda: ["proxy_rotation", "request_throttling", "burst_smoothing"])
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "5")))
    max_concurrent_connections: int = 30
    limit_per_host: int = 6
    connection_pool_size: int = 50
    dns_concurrent_queries: int = 20
    total_timeout: float = 20.0
    connect_timeout: float = 8.0
    read_timeout: float = 15.0
    request_delay_min: float = 0.1
    request_delay_max: float = 0.4
    max_retries: int = 2
    retry_backoff_base: float = 2.0
    retry_backoff_max: float = 10.0
    retry_cooldown: float = 3.0
    cache_ttl: float = 300.0
    use_fragment_api: bool = field(default_factory=lambda: os.getenv("USE_FRAGMENT_API", "true").lower() == "true")
    confirm_available_with_tme: bool = field(default_factory=lambda: os.getenv("CONFIRM_WITH_TME", "true").lower() == "true")
    fragment_timeout: float = 10.0
    rate_limit: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT", "30")))
    rate_limit_backoff_initial: float = 5.0
    rate_limit_backoff_multiplier: float = 2.0
    rate_limit_backoff_max: float = 60.0

ADV_CONFIG = AdvancedConfig()