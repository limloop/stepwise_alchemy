"""
Тестовый источник для отладки пайплайна.
Содержит нормальные данные, мусор, код на Python, смесь языков.
"""

from typing import Iterator, Optional

from core.source_base import BaseSource
from core.registry import register_source


@register_source
class TestDialogueSource(BaseSource):
    name = "test_dialogue"
    quality_tier = 1
    content_type = "dialogue"

    def extract(self) -> Iterator[dict]:
        """Генерирует разнородные сырые записи."""

        # --- 1. Нормальный диалог на русском ---
        yield {
            "lang": "ru",
            "messages": [
                {"role": "user", "content": "Привет! Как дела?"},
                {"role": "assistant", "content": "Здравствуйте! Всё хорошо, спасибо."},
                {"role": "user", "content": "Расскажи про погоду сегодня."},
                {"role": "assistant", "content": "Сегодня солнечно, температура +22°C."},
            ],
        }

        # --- 2. Нормальный диалог на английском ---
        yield {
            "lang": "en",
            "messages": [
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is Paris."},
                {"role": "user", "content": "And what about Germany?"},
                {"role": "assistant", "content": "The capital of Germany is Berlin."},
            ],
        }

        # --- 3. Диалог с Python-кодом (должен быть отбракован) ---
        yield {
            "lang": "ru",
            "messages": [
                {"role": "user", "content": "Напиши функцию сложения."},
                {
                    "role": "assistant",
                    "content": "Вот функция:\n```python\ndef add(a, b):\n    return a + b\n```",
                },
            ],
        }

        # --- 4. Диалог с мусором (случайные символы) ---
        yield {
            "lang": "en",
            "messages": [
                {"role": "user", "content": "Hello!"},
                {
                    "role": "assistant",
                    "content": "asdf@#$%^&*()!!! ??? >>>><<<< ~~~```` №№№%%%%% $$$$$ ¥¥¥¥ °°°° ©©© ®®® ™™™",
                },
            ],
        }

        # --- 5. Диалог со специальными токенами ---
        yield {
            "lang": "ru",
            "messages": [
                {"role": "user", "content": "Привет <|user|>"},
                {
                    "role": "assistant",
                    "content": "[INST] Здравствуйте [/INST] <|endoftext|>",
                },
            ],
        }

        # --- 6. Диалог с URL и email ---
        yield {
            "lang": "en",
            "messages": [
                {"role": "user", "content": "Check this out: https://example.com/page?id=123"},
                {"role": "assistant", "content": "Thanks! Send details to admin@example.com"},
            ],
        }


        # --- 7. Диалог с пустым сообщением ---
        yield {
            "type": "dialogue",
            "lang": "ru",
            "messages": [
                {"role": "user", "content": "Скажи что-нибудь!"},
                {"role": "assistant", "content": ""},
            ],
        }

@register_source
class TestTextSource(BaseSource):
    name = "test_text"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        # --- 1. Нормальный текст на русском ---
        yield {
            "lang": "ru",
            "text": (
                "История этого города насчитывает более тысячи лет. "
                "Первые упоминания встречаются в летописях XII века. "
                "Археологические раскопки подтверждают существование поселения на этом месте "
                "ещё в эпоху неолита. Город пережил множество войн и нашествий, "
                "но каждый раз возрождался из пепла, становясь всё краше."
            ),
        }

        # --- 2. Нормальный текст на английском ---
        yield {
            "lang": "en",
            "text": (
                "The history of artificial intelligence dates back to the mid-20th century. "
                "Alan Turing proposed the famous Turing Test in 1950, asking whether machines "
                "could think. The field has since evolved through several waves of optimism "
                "and disappointment, known as AI winters, before the current deep learning revolution."
            ),
        }

        # --- 3. Текст с мусорными строками вперемешку ---
        yield {
            "lang": "ru",
            "text": (
                "В лесу родилась ёлочка,\n"
                "В лесу она росла.\n"
                "&*&*&*&*&*&*&*\n"
                "Зимой и летом стройная,\n"
                "Зелёная была.\n"
                "!@#!@#!@#!@#!@#\n"
                "Метель ей пела песенку:\n"
                "«Спи, ёлочка, бай-бай!»\n"
            ),
        }

        # --- 4. Пустой текст ---
        yield {
            "lang": "ru",
            "text": "",
        }

        # --- 5. Текст только из спецсимволов ---
        yield {
            "lang": "en",
            "text": "@@@ ### $$$ %%% ^^^ &&& *** --- +++ ===",
        }

        # --- 6. Текст на неподдерживаемом языке (французский) ---
        yield {
            "lang": "fr",
            "text": "Bonjour tout le monde! Comment allez-vous aujourd'hui?",
        }

        # --- 7. Текст с управляющими символами ---
        yield {
            "lang": "ru",
            "text": "Нормальный текст\x00 с управляющим символом\x1F внутри.",
        }

        # --- 8. Текст с множественными пробелами и переносами ---
        yield {
            "lang": "en",
            "text": (
                "This    text    has    too    many    spaces.\n\n\n\n\n"
                "And too many newlines.\n\n\n\n\n"
                "But --- the content ---- is ---- still ---- valid."
            ),
        }