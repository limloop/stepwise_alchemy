from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class ChemistryBookshelvesSource(BaseSource):
    name = "chemistry_bookshelves"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с учебниками по химии.
        Возвращает только текст из поля 'text' (длиннее 100 символов).
        """
        ds = load_dataset(
            "chemNLP/chemistry-bookshelves-merged",
            revision="refs/convert/parquet",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        for example in ds:
            text = example.get("text", "").strip()
            if text and len(text) >= 100:
                # Язык не указан в датасете, но тексты на английском
                yield {"lang": "en", "text": text}