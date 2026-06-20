from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset
import glob
import os

@register_source
class FicbookSource(BaseSource):
    name = "ficbook"
    quality_tier = 2
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с фанфиками с ficbook.net.
        Особенности:
        - description берется как есть (если длина > 100 символов)
        - parts: массив глав, из каждой берется clean_text (если длина > 100 символов)
        
        ВНИМАНИЕ! Перед использованием укажите правильный путь к .parquet файлам:
        - Замените "your_path/*.parquet" на актуальный путь
        - Например: os.path.expanduser("~/data/ficbook/*.parquet")
        """
        
        # TODO: Укажите правильный путь к вашим parquet файлам!
        parquet_folder = "your_path/*.parquet"  # <-- ИЗМЕНИТЕ ЭТУ СТРОКУ!
        
        parquet_files = sorted(glob.glob(parquet_folder))
        
        if not parquet_files:
            raise FileNotFoundError(
                f"No .parquet files found at {parquet_folder}\n"
                "Please update the path in FicbookSource.extract()"
            )

        for file_path in parquet_files:
            ds = load_dataset("parquet", data_files=file_path, split="train")
            
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