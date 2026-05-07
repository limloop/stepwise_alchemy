"""
Валидаторы текста: проверка на мусор, код, допустимые символы.
"""

from cleaners.patterns import WEIRD_CHARS, PYTHON_CODE, DETECTION_PATTERNS
from utils.logging_setup import get_logger

logger = get_logger("cleaners.validators")


def is_valid_text(text: str, threshold: float = 0.8) -> bool:
    """
    Проверяет, является ли текст допустимым (русский/английский).
    Вычисляет долю допустимых символов.
    """
    if not text:
        return False

    matches = WEIRD_CHARS.findall(text)
    return len(matches) / len(text) > threshold


def contains_python_code(text: str) -> bool:
    """Проверяет, содержит ли текст код Python."""
    return bool(PYTHON_CODE.search(text))


def is_garbage_text(text: str, threshold: float = 0.7) -> bool:
    """
    Определяет, является ли текст техническим мусором/шумом.
    Возвращает True, если текст считается мусором.

    Анализирует построчно: если доля «мусорных» строк превышает threshold,
    весь текст считается мусором.
    """
    if not text or len(text.strip()) == 0:
        return True

    lines = text.splitlines()
    if not lines:
        return True

    total_lines = len(lines)
    garbage_lines = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        line_score = 0
        for pattern_name, pattern in DETECTION_PATTERNS.items():
            if pattern.search(line):
                line_score += 1

        # Если линия сработала на нескольких паттернах, считаем её мусорной
        if line_score >= 2:
            garbage_lines += 1

    garbage_ratio = garbage_lines / total_lines if total_lines > 0 else 1.0

    return garbage_ratio > threshold