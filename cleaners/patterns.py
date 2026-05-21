"""
Оптимизированные regex-паттерны для structural cleanup.
Минимум backtracking.
Минимум пересечений.
"""

import re


# ---------------------------------------------------------
# Базовая очистка
# ---------------------------------------------------------

SPECIAL_TOKENS = re.compile(
    r'<\|[^>\n]{1,100}\|>'
    r'|\[(?:INST|/INST|ASST|/ASST|SYS|/SYS)\]'
    r'|<endoftext>'
    r'|<endofprompt>'
    r'|<startoftext>',
    flags=re.IGNORECASE,
)

URL_EMAIL = re.compile(
    r'https?://\S+'
    r'|www\.\S+'
    r'|\S+@\S+',
    flags=re.IGNORECASE,
)

CONTROL_CHARS = re.compile(
    r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]'
)

TECHNICAL = re.compile(
    r'\[\d{1,6}\]'
    r'|\{[^{}\n]{1,100}\}'
)


# ---------------------------------------------------------
# Structural garbage
# ---------------------------------------------------------

# Схлопывание экстремальных повторов
EXTREME_REPEAT = re.compile(
    r'(.)\1{4,}'
)


# Множественные пробелы / переносы
MULTI_SPACES = re.compile(
    r'[ \t]{2,}'
)

MULTI_NEWLINES = re.compile(
    r'\n{2,}'
)


# ---------------------------------------------------------
# Пустые / мусорные скобки и кавычки
# ---------------------------------------------------------

# "", '' , «   » , (   ) и т.д.
EMPTY_QUOTES_BRACKETS = re.compile(
    r'''
    (?:
        ["'«»„”“‘’`]\s*["'«»„”“‘’`]
    )
    |
    (?:
        [\(\[\{<]\s*[\)\]\}>]
    )
    ''',
    flags=re.VERBOSE,
)

# Одиночные кавычки/скобки среди пробелов
LONELY_QUOTES_BRACKETS = re.compile(
    r'''
    (?<=\s)
    ["'«»„”“‘’`\(\)\[\]\{\}<>]
    (?=\s)
    ''',
    flags=re.VERBOSE,
)


# ---------------------------------------------------------
# Пунктуация
# ---------------------------------------------------------

# пробел перед знаками
SPACE_BEFORE_PUNCT = re.compile(
    r'\s+([,.;:!?])'
)

# нет пробела после
SPACE_AFTER_PUNCT = re.compile(
    r'([,;:!?])([^\s])'
)

# точки / многоточия
DOT_SPACE = re.compile(
    r'(\.{3}|\.)([^\s.\d])'
)

# тире без пробела
DASH_SPACE = re.compile(
    r'^([—\-])([^\s])'
)

# код
CODE_HINTS = re.compile(
    r'''
    \b(
        def
        |class
        |import
        |from
        |return
        |lambda
        |async
        |await
    )\b
    |
    [\{\}\[\];]
    ''',
    flags=re.VERBOSE,
)