"""
Валидаторы текста: проверка на мусор, код, допустимые символы.
"""

import re

from cleaners.patterns import CODE_HINTS
from utils.logging_setup import get_logger

logger = get_logger("cleaners.validators")

def is_probably_garbage(text: str) -> bool:

    if not text:
        return True

    text_len = len(text)

    if text_len < 2:
        return True

    # слишком мало букв
    alpha = sum(c.isalpha() for c in text)

    if alpha / text_len < 0.2:
        return True

    # слишком много спецсимволов
    specials = sum(
        not c.isalnum() and not c.isspace()
        for c in text
    )

    if specials / text_len > 0.6:
        return True

    return False

def is_valid_text(text: str, threshold: float = 0.85) -> bool:
    if not text:
        return False

    # быстрый sanity check
    if len(text) < 3:
        return False

    # грубая оценка “битости”
    weird = len(re.findall(r'[^\w\s\u0400-\u04FF.,!?()\-]', text))

    return (1 - weird / len(text)) >= threshold


def contains_python_code(text: str) -> bool:
    if not text:
        return False

    matches = CODE_HINTS.findall(text)

    # density heuristic
    return len(matches) >= 5