from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

@register_source
class GutenbergPoetrySource(BaseSource):
    name = "gutenberg_poetry"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с поэзией из Project Gutenberg.
        Собирает строки (line) в одну книгу, пока gutenberg_id не изменится.
        Использует потоковую обработку, не хранит все книги в памяти.
        """
        ds = load_dataset(
            "biglam/gutenberg-poetry-corpus",
            revision="refs/convert/parquet",
            split="train",
            streaming=True  # Не загружаем всё в память сразу
        )
        
        current_id = None
        current_lines = []
        
        for example in ds:
            gutenberg_id = example.get("gutenberg_id")
            line = example.get("line", "").strip()
            
            if not line:
                continue
            
            # Если началась новая книга
            if current_id is not None and gutenberg_id != current_id:
                # Возвращаем предыдущую книгу
                if current_lines:
                    full_text = " ".join(current_lines)
                    if len(full_text) >= 100:
                        yield {"lang": "en", "text": full_text}
                # Начинаем новую книгу
                current_id = gutenberg_id
                current_lines = [line]
            else:
                # Продолжаем текущую книгу
                if current_id is None:
                    current_id = gutenberg_id
                current_lines.append(line)
        
        # Не забываем про последнюю книгу
        if current_lines:
            full_text = " ".join(current_lines)
            if len(full_text) >= 100:
                yield {"lang": "en", "text": full_text}