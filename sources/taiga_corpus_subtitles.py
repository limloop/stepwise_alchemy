from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset
import pandas as pd

@register_source
class TaigaSubtitlesSource(BaseSource):
    name = "taiga_subtitles"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с субтитрами из Taiga Corpus.
        Собирает строки (text) в один файл/эпизод, пока file_id не изменится.
        Использует потоковую обработку, не хранит все файлы в памяти.
        Объединяет строки через \n (перенос строки), так как это реплики.
        """
        ds = load_dataset(
            "Fascinat0r/taiga_corpus_subtitles",
            revision="refs/convert/parquet",
            split="train",
            streaming=True
        )
        
        batch_size = 50_000
        prev_tail = None  # хранит строки незавершённого file_id
        
        for batch in ds.iter(batch_size=batch_size):
            df = pd.DataFrame(batch)
            
            # Убираем пустые строки
            df = df[df['text'].str.strip().str.len() > 0].copy()
            df['text'] = df['text'].str.strip()
            
            if len(df) == 0:
                continue
            
            # Если есть хвост с прошлого батча, добавляем в начало
            if prev_tail is not None:
                df = pd.concat([prev_tail, df], ignore_index=True)
                prev_tail = None
            
            # Находим последний file_id в батче — он может быть незавершённым
            last_file_id = df['file_id'].iloc[-1]
            
            # Отделяем последний file_id (будет хвостом)
            is_last = df['file_id'] == last_file_id
            prev_tail = df[is_last].copy()
            
            # Всё остальное — завершённые файлы
            completed = df[~is_last]
            
            # Группируем и отдаём завершённые файлы
            for file_id, group in completed.groupby('file_id', sort=False):
                full_text = "\n".join(group['text'].tolist())
                if len(full_text) >= 100:
                    yield {
                        "lang": group['language'].iloc[0],
                        "text": full_text
                    }
        
        # Отдаём последний файл, который остался в хвосте
        if prev_tail is not None and len(prev_tail) > 0:
            full_text = "\n".join(prev_tail['text'].tolist())
            if len(full_text) >= 100:
                yield {
                    "lang": prev_tail['language'].iloc[0],
                    "text": full_text
                }