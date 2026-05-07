"""
Предкомпилированные регулярные выражения для очистки текста.
"""

import re

# Специальные токены
SPECIAL_TOKENS = re.compile(
    r'<\|[^>]+\|>|\[INST\]|\[/INST\]|\[ASST\]|\[/ASST\]|'
    r'\[SYS\]|\[/SYS\]|<endoftext>|<endofprompt>|<startoftext>',
    flags=re.IGNORECASE,
)

# URL и email
URL_EMAIL = re.compile(r'http[s]?://\S+|www\.\S+|\S+@\S+')

# Управляющие символы
CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]')

# Технические артефакты
TECHNICAL = re.compile(r'\[\d+\]|\{[^}]+\}')

# Кавычки (все типы)
QUOTES_REGEX = re.compile(
    r'''
    # Пустые парные кавычки (одинаковые)
    (['"\u00AB\u00BB\u2018-\u201F\u300C\u300D\u301D-\u301F])\s*\1 |

    # Пустые смешанные кавычки (разные, но подряд)
    (['"]\s*[\u00AB\u00BB\u2018-\u201F\u300C\u300D\u301D-\u301F]) |
    ([\u00AB\u00BB\u2018-\u201F\u300C\u300D\u301D-\u301F]\s*['"]) |

    # Одиночные кавычки без текста (в начале/конце строки или окружённые пробелами)
    (^|\s)(['"\u00AB\u00BB\u2018-\u201F\u300C\u300D\u301D-\u301F])($|\s)
    ''',
    flags=re.VERBOSE,
)

# Скобки
BRACKETS_REGEX = re.compile(
    r'''
    # Пустые скобки (любые типы)
    \([ \t]*\) |   # ()
    \[[ \t]*\] |   # []
    \{[ \t]*\} |   # {}
    \<[ \t]*\> |   # <>

    # Скобки с разделителями внутри (например, (,,,), [; ])
    \([ \t]*[;:,]+[ \t]*\) |
    \[[ \t]*[;:,]+[ \t]*\] |
    \{[ \t]*[;:,]+[ \t]*\} |

    # Одиночные скобки без пары (только если стоят в начале/конце строки)
    (^|\s)([(\[{<])($|\s) |
    (^|\s)([)\]}>])($|\s)
    ''',
    flags=re.VERBOSE,
)

# Скобки с разделителями (для очистки содержимого)
EMPTY_BRACKETS = re.compile(r'\(\s*[;:,]+\s*\)')
CLEAN_BRACKETS_START = re.compile(r'\(\s*[;:,]+\s*([^;:,)]+?)\s*[;:,]*\s*\)')
CLEAN_BRACKETS_END = re.compile(r'\(\s*([^;:,)]+)\s*[;:,]+\s*\)')

# Множественные символы
MULTIPLE_SPACES = re.compile(r' {2,}')
MULTIPLE_DASHES = re.compile(r'-{4,}')
MULTIPLE_UNDERSCORES = re.compile(r'_{4,}')
MULTIPLE_NEWLINES = re.compile(r'\n{3,}')

# Пунктуация и пробелы
SPACES_BEFORE_PUNCT = re.compile(r'\s+([.,!?;:])')
SPACES_AFTER_PUNCT = re.compile(r'([.,!?;:])\s+')

# Python-код
PYTHON_CODE = re.compile(
    r'(\b(def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+\s+import)\b|#.*|\"{3}[\s\S]*?\"{3})'
)

# Паттерны для определения мусорного текста
DETECTION_PATTERNS = {
    # Сочетания цифр, символов и букв в случайном порядке
    'RANDOM_CHAR_SEQUENCES': re.compile(
        r'\b(?:\w*[0-9\$¥€°]+\w*[A-Za-z]+\w*|\w*[A-Za-z]+\w*[0-9\$¥€°]+\w*){2,}\b'
    ),
    # Слишком много цифр или специальных символов подряд относительно всего текста
    'HIGH_DENSITY_NON_WORD': re.compile(
        r'(?:[0-9\$¥€°©®™§§©®™§&*@#%^\+=\\\/\{\}\[\]<>~`]{3,})'
    ),
    # Множественные одиноко стоящие кавычки, пунктуация
    'LONELY_QUOTES_PUNCT': re.compile(
        r'(?:\s[\'\"\‘\’\`]+\s)|(?:^[\'\"\‘\’\`]+\s)|(?:\s[\'\"\‘\’\`]+$)'
    ),
    # Строки, состоящие почти целиком из не-алфавитных символов
    'NON_ALPHA_LINES': re.compile(r'^\s*[^A-Za-z\s]{5,}.*$', re.MULTILINE),
}

# Допустимые символы (для is_valid_text)
WEIRD_CHARS = re.compile(
    r'''
    [\u0400-\u04FF\u0500-\u052F]|
    [a-zA-Z]|
    [0-9]|
    [\s\.,!?\'\"\-:;()]
    ''',
    re.VERBOSE,
)