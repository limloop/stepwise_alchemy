"""
Функции очистки текста.
"""

import unicodedata

from cleaners.patterns import (
    SPECIAL_TOKENS,
    URL_EMAIL,
    CONTROL_CHARS,
    TECHNICAL,
    EXTREME_REPEAT,
    MULTI_SPACES,
    MULTI_NEWLINES,
    EMPTY_QUOTES_BRACKETS,
    LONELY_QUOTES_BRACKETS,
    SPACE_BEFORE_PUNCT,
    SPACE_AFTER_PUNCT,
    DOT_SPACE,
    DASH_SPACE
)

from cleaners.validators import is_probably_garbage


MAX_TEXT_LEN = 100_000


def clean_text(text: str) -> str:
    """
    Structural cleanup текста.

    Цель:
    - убрать технический шум
    - нормализовать пунктуацию
    - уменьшить structural entropy
    - не уничтожать естественный шум полностью
    """

    if not text:
        return ""

    # ---------------------------------------------------------
    # Hard limit
    # ---------------------------------------------------------

    if len(text) > MAX_TEXT_LEN:
        return ""

    # ---------------------------------------------------------
    # Быстрая проверка мусора ДО regex
    # ---------------------------------------------------------

    if is_probably_garbage(text):
        return ""

    # ---------------------------------------------------------
    # Unicode normalization
    # ---------------------------------------------------------

    text = unicodedata.normalize("NFKC", text)

    # ---------------------------------------------------------
    # Базовая очистка
    # ---------------------------------------------------------

    text = SPECIAL_TOKENS.sub("", text)
    text = URL_EMAIL.sub("", text)
    text = CONTROL_CHARS.sub("", text)
    text = TECHNICAL.sub("", text)

    # ---------------------------------------------------------
    # Structural cleanup
    # ---------------------------------------------------------

    # ♥♥♥♥♥♥♥♥ -> ♥♥♥
    text = EXTREME_REPEAT.sub(
        lambda m: m.group(1) * 3,
        text,
    )

    # ---------------------------------------------------------
    # Пустые структуры
    # ---------------------------------------------------------

    text = EMPTY_QUOTES_BRACKETS.sub("", text)
    text = LONELY_QUOTES_BRACKETS.sub(" ", text)

    # ---------------------------------------------------------
    # Пунктуация
    # ---------------------------------------------------------

    # "странами , но" -> "странами, но"
    text = SPACE_BEFORE_PUNCT.sub(r"\1", text)

    # "ниндзя;броня" -> "ниндзя; броня"
    text = SPACE_AFTER_PUNCT.sub(r"\1 \2", text)

    # "там...Но" -> "там... Но"
    text = DOT_SPACE.sub(r"\1 \2", text)

    # "-Эм" -> "- Эм"
    text = DASH_SPACE.sub(r"\1 \2", text)

    # ---------------------------------------------------------
    # Финальная нормализация
    # ---------------------------------------------------------

    text = MULTI_SPACES.sub(" ", text)
    text = MULTI_NEWLINES.sub("\n", text)

    return text.strip()