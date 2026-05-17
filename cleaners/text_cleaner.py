"""
Функции очистки текста.
"""

import unicodedata

from cleaners.patterns import (
    CONTROL_CHARS,
    SPECIAL_TOKENS,
    URL_EMAIL,
    EMPTY_BRACKETS,
    EMPTY_QUOTES,
    MULTISPACE,
    MULTINEWLINE
)
from utils.logging_setup import get_logger

logger = get_logger("cleaners.text_cleaner")

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)

    # быстрый reject мусора
    text = CONTROL_CHARS.sub('', text)
    text = SPECIAL_TOKENS.sub('', text)

    if not text:
        return ""

    # структурные артефакты
    text = URL_EMAIL.sub('', text)

    # удаление пустых конструкций
    text = EMPTY_BRACKETS.sub('', text)
    text = EMPTY_QUOTES.sub('', text)

    # нормализация whitespace
    text = MULTISPACE.sub(' ', text)
    text = MULTINEWLINE.sub('\n\n', text)

    return text.strip()