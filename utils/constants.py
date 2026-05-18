"""
Constants and enumerations for the scanner bot.
"""
from enum import Enum

class ScanStatus(Enum):
    IDLE = "idle"
    RUNNING = "🔄 يعمل"
    PAUSED = "⏸️ متوقف مؤقتاً"
    STOPPING = "stopping"
    STOPPED = "⏹️ موقوف"
    COMPLETED = "✅ مكتمل"
    ERROR = "❌ خطأ"

class UsernameStatus(Enum):
    AVAILABLE = "available"
    TAKEN = "taken"
    RESERVED = "reserved"
    INVALID = "invalid"
    UNKNOWN = "unknown"

class Confidence(Enum):
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5

TELEGRAM_ENDPOINTS = {
    "t_me": "https://t.me/",
    "telegram_org": "https://telegram.org/",
    "fragment": "https://fragment.com/username/",
}

PATTERN_CHARS = {
    '$': 'abcdefghijklmnopqrstuvwxyz',
    '#': '0123456789'
}

FINGERPRINTS = ["chrome_120", "firefox_121", "safari_17"]
SCANNER_MESSAGES = {
    "welcome": "👋 أهلاً بك في **Telegram Username Scanner Pro**\n\nابدأ بفحص جديد من القائمة أدناه 👇",
    "error": "❌ حدث خطأ غير متوقع.",
    "no_active": "⚠️ لا توجد فحوصات نشطة حالياً.",
}