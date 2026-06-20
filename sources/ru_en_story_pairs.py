from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class RuEnStoryPairsSource(BaseSource):
    name = "ru_en_story_pairs"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с параллельными русско-английскими историями.
        Возвращает 4 типа текстов для каждого примера:
        - text_ru (русский рассказ)
        - text_en (английская адаптация)
        - summary_ru (русское краткое содержание)
        - summary_en (английское краткое содержание)
        """
        ds = load_dataset(
            "limloop/ru_en_story_pairs",
            revision="refs/convert/parquet",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        for example in ds:
            # Русский рассказ
            text_ru = example.get("text_ru", "").strip()
            if text_ru and len(text_ru) >= 100:
                yield {"lang": "ru", "text": text_ru}
            
            # Английская адаптация
            text_en = example.get("text_en", "").strip()
            if text_en and len(text_en) >= 100:
                yield {"lang": "en", "text": text_en}
            
            # Русское краткое содержание
            summary_ru = example.get("summary_ru", "").strip()
            if summary_ru and len(summary_ru) >= 100:
                yield {"lang": "ru", "text": summary_ru}
            
            # Английское краткое содержание
            summary_en = example.get("summary_en", "").strip()
            if summary_en and len(summary_en) >= 100:
                yield {"lang": "en", "text": summary_en}