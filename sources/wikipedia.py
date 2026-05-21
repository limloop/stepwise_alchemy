from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset
import re

@register_source
class WikipediaSource(BaseSource):
    name = "wikipedia"
    quality_tier = 3
    content_type = "text"

    def extract(self):
        """
        Загружает датасет Wikipedia для нескольких языков.
        Особенности:
        - Базовые языки: до 50k строк каждый
        - en и ru: до 100k строк
        - Обрезка текста до "См. также" или аналогичных маркеров
        """
        
        # Конфигурация языков: (код, максимальное количество строк)
        languages = [
            ("en", 500000),
            ("ru", 500000),
            ("de", 50000),
            ("fr", 50000),
            ("es", 50000),
            ("it", 50000),
            ("pt", 50000),
            ("pl", 50000),
            ("uk", 50000),
            ("ja", 50000),
            ("zh", 50000),
            ("ar", 50000),
        ]
        
        # Маркеры обрезки для разных языков
        stop_markers = {
            "default": [
                "См. также",
                "See also",
                "Siehe auch",
                "Voir aussi",
                "Ver también",
                "Vedi anche",
                "Veja também",
                "Zobacz też",
                "Див. також",
                "関連項目",
                "参见",
                "انظر أيضًا",
            ],
            "ru": ["См. также", "Примечания", "Ссылки", "Литература"],
            "en": ["See also", "References", "External links", "Notes", "Further reading"],
            "de": ["Siehe auch", "Literatur", "Weblinks", "Einzelnachweise"],
            "fr": ["Voir aussi", "Notes et références", "Liens externes", "Bibliographie"],
            "es": ["Véase también", "Referencias", "Enlaces externos", "Bibliografía"],
            "it": ["Voci correlate", "Note", "Altri progetti", "Collegamenti esterni"],
            "pt": ["Ver também", "Referências", "Ligações externas", "Bibliografia"],
            "pl": ["Zobacz też", "Przypisy", "Linki zewnętrzne", "Bibliografia"],
            "uk": ["Див. також", "Примітки", "Посилання", "Література"],
            "ja": ["関連項目", "脚注", "外部リンク", "参考文献"],
            "zh": ["参见", "参考资料", "外部链接", "参考文献"],
            "ar": ["انظر أيضًا", "مراجع", "وصلات خارجية", "ملاحظات"],
        }
        
        for lang, max_rows in languages:
            try:
                # Формируем имя subset (используем актуальную дату дампа)
                subset_name = f"20231101.{lang}"
                
                # Загружаем датасет в streaming режиме
                ds = load_dataset(
                    "wikimedia/wikipedia", 
                    subset_name, 
                    split="train"
                )
                
                # Получаем маркеры для текущего языка
                markers = stop_markers.get(lang, stop_markers["default"])
                
                count = 0
                for example in ds:
                    if count >= max_rows:
                        break
                    
                    text = example.get("text", "").strip()
                    if not text or len(text) < 100:
                        continue
                    
                    # Обрезаем текст до первого маркера
                    text = self._truncate_at_marker(text, markers)
                    
                    if len(text) >= 100:
                        yield {"lang": lang, "text": text}
                        count += 1
                        
            except Exception as e:
                print(f"Error loading language {lang}: {e}")
                continue
    
    def _truncate_at_marker(self, text, markers):
        """
        Обрезает текст до первого найденного маркера.
        Ищет маркеры как отдельные строки или в начале строки.
        """
        lines = text.split('\n')
        result_lines = []
        
        for line in lines:
            # Проверяем, не начинается ли строка с маркера
            should_stop = False
            for marker in markers:
                # Проверяем точное совпадение или начало строки с маркером
                if line.strip().startswith(marker) or line.strip() == marker:
                    should_stop = True
                    break
            
            if should_stop:
                break
            
            result_lines.append(line)
        
        return '\n'.join(result_lines).strip()