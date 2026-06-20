from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class TokEnStoryPairsSource(BaseSource):
    name = "tokipona_en_ru_story"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с параллельными английскими-токипона историями.
        Возвращает токипона перевод для каждого примера, так как истории есть в ru_en_story_pairs
        """
        ds = load_dataset(
            "limloop/tokipona_en_ru_story",
            revision="refs/convert/parquet",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        for example in ds:
            # Русский рассказ
            text = example.get("translated_text", "").strip()
            if text and len(text) >= 100:
                yield {"lang": "tok", "text": text}