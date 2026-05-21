from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset

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
        languages = ["ru", "en", "it", "de"]
        
        for lang in languages:
            # Загружаем split для каждого языка отдельно
            ds = load_dataset(
                "Fascinat0r/taiga_corpus_subtitles", 
                split=lang
            )
            
            current_file_id = None
            current_lines = []
            current_lang = lang
            
            for example in ds:
                file_id = example.get("file_id")
                text = example.get("text", "").strip()
                
                if not text:
                    continue
                
                # Если начался новый файл
                if current_file_id is not None and file_id != current_file_id:
                    # Возвращаем предыдущий файл
                    if current_lines:
                        full_text = "\n".join(current_lines)
                        if len(full_text) >= 100:
                            yield {"lang": current_lang, "text": full_text}
                    
                    # Начинаем новый файл
                    current_file_id = file_id
                    current_lines = [text]
                else:
                    # Продолжаем текущий файл
                    if current_file_id is None:
                        current_file_id = file_id
                    current_lines.append(text)
            
            # Не забываем про последний файл в текущем языке
            if current_lines:
                full_text = "\n".join(current_lines)
                if len(full_text) >= 100:
                    yield {"lang": current_lang, "text": full_text}