"""
Known reserved / system-held Telegram usernames.
"""
RESERVED_PREFIXES: frozenset = frozenset({
    "tg", "tgram", "tgchannel", "tggroup", "tguser", "telega", "telegra",
    "t_me", "tme", "telegramdeveloper", "telegramdesktop", "tdesktop",
    "telegram", "durov", "staff", "office", "legal", "press", "dmca",
    "copyright", "trademark", "verified", "verify",
    "admin", "admins", "administrator", "administrators", "superadmin",
    "moderator", "moderators", "mod", "mods", "owner", "manager",
    "managers", "operator", "operators", "sysadmin", "root", "system",
    "server", "host",
    "support", "supports", "help", "helpdesk", "service", "services",
    "contact", "contacts", "info", "information", "faq", "feedback",
    "report", "reports", "abuse", "spam", "nospam", "antispam",
    "security", "privacy", "policy", "terms", "tos", "status",
    "online", "offline", "away", "busy",
    "account", "profile", "settings", "config", "login", "logout",
    "signin", "signup", "register", "password", "secret", "private",
    "public", "premium", "gift", "stars", "wallet", "fragment",
    "auction", "username", "usernames", "channel", "group", "bot", "user",
    "test", "beta", "dev", "developer", "api", "sandbox", "testing",
    "search", "find", "explore", "discover", "home", "index", "about",
    "shop", "store", "market", "buy", "sell", "pay", "payment",
    "billing", "invoice", "mail", "email", "message", "chat", "call",
    "video", "audio", "photo", "image", "file", "data", "stats",
    "analytics", "broadcast", "forward", "reply", "mention",
    "russia", "usa", "uk", "uae", "iran", "turkey", "china",
    "arabic", "english", "russian", "persian"
})

def is_reserved(username: str) -> bool:
    u = username.lower().strip()
    u_clean = u.strip('_')

    for prefix in RESERVED_PREFIXES:
        if u.startswith(prefix) or u_clean.startswith(prefix):
            return True

    common_dead_words = {"admin", "telegram", "support", "bot"}
    for word in common_dead_words:
        if word in u:
            return True

    return False