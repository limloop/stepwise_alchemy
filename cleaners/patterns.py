import re

# технические токены (минимальный набор)
SPECIAL_TOKENS = re.compile(
    r'<\|[^>]+\|>|\[/?(INST|ASST|SYS)\]|<endoftext>|<startoftext>',
    re.IGNORECASE,
)

URL_EMAIL = re.compile(r'https?://\S+|www\.\S+|\S+@\S+')

CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')

# структурный мусор (только реально нужное)
EMPTY_BRACKETS = re.compile(
    r'\(\s*\)|\[\s*\]|\{\s*\}|<\s*>'
)

EMPTY_QUOTES = re.compile(
    r'(["\'«»“”‘’])\s*\1'
)

MULTISPACE = re.compile(r' {2,}')
MULTINEWLINE = re.compile(r'\n{3,}')

PYTHON_CODE = re.compile(
    r'\b(def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+)\b'
)