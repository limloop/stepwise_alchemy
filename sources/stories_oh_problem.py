from core.source_base import BaseSource
from core.registry import register_source
from datasets import load_dataset
import hashlib

@register_source
class StoriesOhProblemSource(BaseSource):
    name = "stories_oh_problem"
    quality_tier = 1
    content_type = "text"

    def extract(self):
        """
        Загружает датасет с историями для решения проблем.
        Особенности:
        - completion используется как есть
        - prompt_problem_solving_story дедуплицируется через set хешей
        - уникальные истории записываются как отдельные записи
        """
        ds = load_dataset("loubnabnl/stories_oh_problem", split="train")
        
        # Set для хранения хешей уже обработанных prompt_problem_solving_story
        seen_hashes = set()
        
        for example in ds:
            # Обработка completion (берем как есть)
            completion = example.get("completion", "").strip()
            if completion and len(completion) >= 100:
                yield {"lang": "en","text": completion}
            
            # Обработка prompt_problem_solving_story с дедупликацией
            prompt_story = example.get("prompt_problem_solving_story", "").strip()
            if prompt_story and len(prompt_story) >= 100:
                # Создаем хеш для сравнения
                story_hash = hashlib.md5(prompt_story.encode('utf-8')).hexdigest()
                
                if story_hash not in seen_hashes:
                    seen_hashes.add(story_hash)
                    yield {"lang": "en", "text": prompt_story}