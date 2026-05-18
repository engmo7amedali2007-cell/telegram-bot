"""
Username generator with async streaming and Telegram validation.
"""
import asyncio
import itertools
import random
from typing import List, AsyncIterator
from .pattern_parser import PatternParser, ParsedPattern
from utils.logger import logger
from utils.constants import PATTERN_CHARS
from utils.reserved_usernames import is_reserved

class UsernameGenerator:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.parsed = PatternParser.parse(pattern)
        self.character_sets = self._build_character_sets()
        self.raw_combinations_count = self.parsed.total_combinations

    def _build_character_sets(self) -> List[List[str]]:
        char_sets = []
        i = 0
        while i < len(self.pattern):
            char = self.pattern[i]
            if char == '$':
                letters = list(PATTERN_CHARS['$'])
                count = 1
                while i + 1 < len(self.pattern) and self.pattern[i + 1] == '$':
                    count += 1; i += 1
                for _ in range(count): char_sets.append(letters)
            elif char == '#':
                digits = list(PATTERN_CHARS['#'])
                count = 1
                while i + 1 < len(self.pattern) and self.pattern[i + 1] == '#':
                    count += 1; i += 1
                for _ in range(count): char_sets.append(digits)
            elif char == '_':
                count = 1
                while i + 1 < len(self.pattern) and self.pattern[i + 1] == '_':
                    count += 1; i += 1
                for _ in range(count): char_sets.append(['_'])
            else:
                char_sets.append([char.lower()])
            i += 1
        return char_sets

    async def generate_chunks(self, chunk_size: int = 100) -> AsyncIterator[List[str]]:
        product_iterator = itertools.product(*self.character_sets)
        buffer_size = chunk_size * 10
        buffer = []

        for combo in product_iterator:
            username = ''.join(combo)
            if PatternParser.validate_username(username) and not is_reserved(username):
                buffer.append(username)

            if len(buffer) >= buffer_size:
                random.shuffle(buffer)
                while len(buffer) >= chunk_size:
                    yield buffer[:chunk_size]
                    buffer = buffer[chunk_size:]
                    await asyncio.sleep(0)

        if buffer:
            random.shuffle(buffer)
            while buffer:
                yield buffer[:chunk_size]
                buffer = buffer[chunk_size:]
                await asyncio.sleep(0)

    @property
    def is_valid(self) -> bool: return self.parsed.is_valid
    @property
    def error_message(self) -> str: return self.parsed.error_message
    @property
    def total_combinations(self) -> int: return self.raw_combinations_count