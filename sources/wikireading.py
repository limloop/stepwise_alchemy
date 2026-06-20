import io
import json
from pathlib import Path

import zstandard as zstd
from tqdm import tqdm
from fast_langdetect import detect

from core.source_base import BaseSource
from core.registry import register_source


@register_source
class WikiReadingSource(BaseSource):
    name = "wikireading"
    quality_tier = 2
    content_type = "text"

    MIN_TEXT_LEN = 100
    
    # ВНИМАНИЕ! Укажите правильный путь к файлам датасета wikireading!
    DATA_DIR = Path("your_path")  # <-- ИЗМЕНИТЕ!

    def _iter_zst_file(self, path: Path):
        """
        Потоковое чтение jsonl.zst без загрузки в RAM.
        """

        with open(path, "rb") as fh:
            dctx = zstd.ZstdDecompressor()

            with dctx.stream_reader(fh) as reader:
                text_stream = io.TextIOWrapper(
                    reader,
                    encoding="utf-8"
                )

                for line in text_stream:
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    text = obj.get("text")

                    if not text:
                        continue

                    text = text.strip()

                    if len(text) < self.MIN_TEXT_LEN:
                        continue

                    yield text

    def extract(self):
        """
        Полностью потоковая обработка:
        zst -> json -> detect -> yield

        RAM usage ≈ constant.
        
        ВНИМАНИЕ! Перед использованием:
        1. Проверьте, что DATA_DIR указывает на правильную папку с .jsonl.zst файлами
        2. Или переопределите DATA_DIR при создании экземпляра класса
        """

        zst_files = sorted(self.DATA_DIR.glob("*.jsonl.zst"))

        if not zst_files:
            raise FileNotFoundError(
                f"No .jsonl.zst files found in {self.DATA_DIR}\n"
                "Please update WikiReadingSource.DATA_DIR with the correct path"
            )

        file_pbar = tqdm(
            zst_files,
            desc="Files",
            unit="file"
        )

        total = 0

        for zst_path in file_pbar:

            text_iter = self._iter_zst_file(zst_path)

            text_pbar = tqdm(
                text_iter,
                desc=zst_path.name,
                unit="texts",
                leave=False
            )

            for text in text_pbar:

                try:
                    result = detect(
                        text,
                        model="lite",
                        k=1
                    )

                    lang = result[0]["lang"]

                except Exception:
                    lang = "unknown"

                yield {
                    "lang": lang,
                    "text": text
                }

                total += 1

                if total % 1000 == 0:
                    text_pbar.set_postfix({
                        "total": total
                    })

        print(f"Processed texts: {total:,}")