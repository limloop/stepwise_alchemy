from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset
import glob

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
        """

        parquet_folder = "/home/arsen/.cache/huggingface/hub/datasets--IlyaGusev--ficbook/snapshots/7451f418e9d0b59683aa3b2f813603bc6124e93b/default/train/*.parquet"
        parquet_files = sorted(glob.glob(parquet_folder))

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