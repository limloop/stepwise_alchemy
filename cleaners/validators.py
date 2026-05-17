"""
Валидаторы текста: проверка на мусор, код, допустимые символы.
"""

import re

from cleaners.patterns import PYTHON_CODE
from utils.logging_setup import get_logger

logger = get_logger("cleaners.validators")


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
    return bool(PYTHON_CODE.search(text))