from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class FantasyBodyInteractionsSource(BaseSource):
    name = "fantasy_body_interactions"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с описаниями телесных взаимодействий.
        Берет только поле text (сгенерированный текст).
        """
        ds = load_dataset(
            "limloop/fantasy_body_interactions",
            revision="refs/convert/parquet",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        for example in ds:
            text = example.get("text", "").strip()
            if text and len(text) >= 100:
                yield {"lang": "ru", "text": text}