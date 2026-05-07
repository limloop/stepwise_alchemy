"""
Функции очистки текста.
"""

import unicodedata

from cleaners.patterns import (
    SPECIAL_TOKENS,
    URL_EMAIL,
    CONTROL_CHARS,
    TECHNICAL,
    QUOTES_REGEX,
    BRACKETS_REGEX,
    EMPTY_BRACKETS,
    CLEAN_BRACKETS_START,
    CLEAN_BRACKETS_END,
    MULTIPLE_SPACES,
    MULTIPLE_DASHES,
    MULTIPLE_UNDERSCORES,
    MULTIPLE_NEWLINES,
    SPACES_BEFORE_PUNCT,
    SPACES_AFTER_PUNCT,
)
from cleaners.validators import is_garbage_text
from utils.logging_setup import get_logger

logger = get_logger("cleaners.text_cleaner")

def clean_text(text: str) -> str:
    """
    Удаляет технические артефакты, сохраняя исходное форматирование текста.
    Возвращает пустую строку, если текст признан мусором.
    """
    if not text:
        return ""

    # Проверка на мусор
    if is_garbage_text(text):
        return ""

    # Удаляем специальные токены
    text = SPECIAL_TOKENS.sub('', text)

    # Удаляем URL и email
    text = URL_EMAIL.sub('', text)

    # Удаляем управляющие символы
    text = CONTROL_CHARS.sub('', text)

    # Удаляем технические артефакты
    text = TECHNICAL.sub('', text)

    # Удаляем пустые кавычки и скобки
    text = QUOTES_REGEX.sub('', text)
    text = BRACKETS_REGEX.sub('', text)

    # Нормализуем юникод
    text = unicodedata.normalize("NFKC", text)

    # Обрабатываем скобки
    text = EMPTY_BRACKETS.sub('', text)
    text = CLEAN_BRACKETS_START.sub(r'(\1)', text)
    text = CLEAN_BRACKETS_END.sub(r'(\1)', text)

    # Удаляем множественные символы
    text = MULTIPLE_SPACES.sub(' ', text)
    text = MULTIPLE_DASHES.sub('---', text)
    text = MULTIPLE_UNDERSCORES.sub('___', text)
    text = MULTIPLE_NEWLINES.sub('\n\n', text)

    # Обрабатываем пробелы вокруг пунктуации
    text = SPACES_BEFORE_PUNCT.sub(r'\1', text)
    text = SPACES_AFTER_PUNCT.sub(r'\1 ', text)

    return text.strip()