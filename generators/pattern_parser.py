"""
Advanced pattern parser with validation and expansion.
"""
import re
from typing import List, Tuple
from dataclasses import dataclass
from utils.constants import PATTERN_CHARS
from utils.logger import logger

@dataclass
class ParsedPattern:
    original: str
    parts: List[Tuple[str, int]]
    total_combinations: int
    min_length: int
    max_length: int
    is_valid: bool
    error_message: str = ""

class PatternParser:
    MIN_USERNAME_LENGTH = 5
    MAX_USERNAME_LENGTH = 32
    VALID_STATIC_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')
    _TELEGRAM_RE = re.compile(r'^[a-z0-9][a-z0-9_]{3,30}[a-z0-9]$')

    @classmethod
    def parse(cls, pattern: str) -> ParsedPattern:
        valid_pattern_chars = set('$_#') | cls.VALID_STATIC_CHARS
        invalid_chars = set(pattern) - valid_pattern_chars
        if invalid_chars:
            return cls._error(pattern, f"رموز غير صالحة: {', '.join(invalid_chars)}. استخدم فقط: $ (حرف), # (رقم), _ (شرطة سفلية), a-z, A-Z, 0-9")

        parts = []
        total_combinations = 1
        i = 0
        while i < len(pattern):
            char = pattern[i]
            if char in ('$', '#', '_'):
                count = 1
                while i + 1 < len(pattern) and pattern[i + 1] == char:
                    count += 1
                    i += 1
                parts.append((char, count))
                if char == '$': total_combinations *= (26 ** count)
                elif char == '#': total_combinations *= (10 ** count)
                elif char == '_': total_combinations *= (1 ** count)
            else:
                parts.append((char, 1))
            i += 1

        static_count = sum(count for char, count in parts if char not in ('$', '#', '_'))
        placeholder_count = sum(count for char, count in parts if char in ('$', '#', '_'))
        actual_length = placeholder_count + static_count

        if actual_length < cls.MIN_USERNAME_LENGTH:
            return cls._error(pattern, f"طول اليوزر {actual_length} - الحد الأدنى {cls.MIN_USERNAME_LENGTH}")
        if actual_length > cls.MAX_USERNAME_LENGTH:
            return cls._error(pattern, f"طول اليوزر {actual_length} - الحد الأقصى {cls.MAX_USERNAME_LENGTH}")
        if total_combinations > 1_000_000:
            return cls._error(pattern, f"عدد التوليفات كبير جداً ({total_combinations:,}). الحد الأقصى: 1,000,000")

        return ParsedPattern(original=pattern, parts=parts, total_combinations=total_combinations, min_length=actual_length, max_length=actual_length, is_valid=True)

    @classmethod
    def _error(cls, pattern: str, message: str) -> ParsedPattern:
        return ParsedPattern(original=pattern, parts=[], total_combinations=0, min_length=0, max_length=0, is_valid=False, error_message=message)

    @classmethod
    def validate_username(cls, username: str) -> bool:
        u = username.lower()
        if len(u) < cls.MIN_USERNAME_LENGTH or len(u) > cls.MAX_USERNAME_LENGTH: return False
        if not cls._TELEGRAM_RE.match(u): return False
        if '__' in u: return False
        return True