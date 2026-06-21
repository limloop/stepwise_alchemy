from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class BooksSummarizationRUSource(BaseSource):
    name = "booksummarization_ru"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с книгами и их суммаризациями.
        Для каждого примера возвращает две записи:
        - полный текст книги (full_text)
        - суммаризацию (summary)
        Все тексты на русском языке.
        """
        ds = load_dataset(
            "slon-hk/BooksSummarizationRU",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        for example in ds:
            full_text = example.get("Full Text", "").strip()
            summary = example.get("Summary", "").strip()
            
            # Валидация полного текста
            if full_text and len(full_text) >= 100:
                yield {"lang": "ru", "text": full_text}
            
            # Валидация суммаризации
            if summary and len(summary) >= 100:
                yield {"lang": "ru", "text": summary}