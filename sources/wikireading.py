from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset
from fast_langdetect import detect

@register_source
class WikiReadingSource(BaseSource):
    name = "wikireading"
    quality_tier = 2
    content_type = "text"

    MIN_TEXT_LEN = 100

    def extract(self):
        """
        Загружает датасет WikiReading через Hugging Face.
        Использует потоковую загрузку для экономии памяти.
        
        Особенности:
        - Берёт поле "text" из каждого примера
        - Автоматически определяет язык через fast_langdetect
        - Фильтрует слишком короткие тексты
        """
        # Загружаем датасет с Hugging Face
        ds = load_dataset(
            "its5Q/wikireading",
            split="train",
            streaming=True  # Потоковая загрузка
        )
        
        for example in ds:
            text = example.get("text", "").strip()
            
            # Фильтруем по длине
            if len(text) < self.MIN_TEXT_LEN:
                continue
            
            # Определяем язык
            try:
                result = detect(text, model="lite", k=1)
                lang = result[0]["lang"]
            except Exception:
                lang = "unknown"
            
            yield {"lang": lang, "text": text}