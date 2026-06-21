from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class FicbookSource(BaseSource):
    name = "ficbook"
    quality_tier = 2
    content_type = "text"

    def extract(self):
        """
        Загружает сжатый датасет с фанфиками с ficbook.net через Hugging Face.
        Использует оптимизированную ветку refs/convert/parquet (~3 ГБ).
        
        Особенности:
        - description берется как есть (если длина > 100 символов)
        - parts: массив глав, из каждой берется clean_text (если длина > 100 символов)
        - Использует потоковую загрузку (streaming=True) для экономии памяти
        """
        # Загружаем датасет из правильной ветки с parquet-файлами
        ds = load_dataset(
            "IlyaGusev/ficbook",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        for example in ds:
            # Обработка description
            description = example.get("description", "").strip()
            if description and len(description) >= 100:
                yield {"lang": "ru", "text": description}
            
            # Обработка частей (глав)
            parts = example.get("parts", [])
            for part in parts:
                if isinstance(part, dict):
                    clean_text = part.get("clean_text", "").strip()
                    if clean_text and len(clean_text) >= 100:
                        yield {"lang": "ru", "text": clean_text}