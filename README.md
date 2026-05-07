# StepWise Alchemy

Модульный пайплайн для загрузки, очистки и сборки датасетов.

## Установка

```bash
git clone https://github.com/limloop/stepwise_alchemy.git
cd stepwise_alchemy
pip install -r requirements.txt
```

## Быстрый старт

```bash
# Полный прогон тестового источника (этапы 1+2+3)
python stepwise.py --stage all

# Только загрузка и очистка
python stepwise.py --stage 1,2

# Конкретный источник
python stepwise.py --source wikipedia_ru --stage 1,2

# Только сборка в режиме chat
python stepwise.py --stage 3 --mode chat

# Принудительная переобработка
python stepwise.py --source my_source --stage 1,2 --force
```

## Архитектура

### Этапы

| Этап | Команда | Описание |
|------|---------|----------|
| 1 — Extract | `--stage 1` | Загрузка сырых данных из источников → `cache/<name>/raw.parquet` |
| 2 — Clean | `--stage 2` | Очистка и валидация → `cache/<name>/cleaned.parquet` |
| 3 — Assembly | `--stage 3` | Сборка финального датасета в режимах `chat` и/или `text` |

### Режимы сборки (этап 3)

- **chat** — диалоги для инструкционного обучения. Сохраняются как `output/chat/dialogues.parquet`
- **text** — сплошной текст с нарезкой на чанки. Сохраняются как `output/text/chunks_<N>.parquet`

```bash
python stepwise.py --stage 3 --mode chat        # только диалоги
python stepwise.py --stage 3 --mode text        # только текст
python stepwise.py --stage 3 --mode chat,text   # оба
```

### Кеширование

Каждый источник кешируется независимо. При повторном запуске пройденные этапы пропускаются.

```
cache/
  ru_en_story_pairs/
    raw.parquet
    cleaned.parquet
    metadata.json
  wikipedia_ru/
    raw.parquet
    cleaned.parquet
    metadata.json
```

### Качество и пропорции

Источники имеют уровень качества (`quality_tier`):
- **Tier 1** — высокое качество (например, размеченные вручную)
- **Tier 2** — среднее
- **Tier 3** — низкое (например, сырая википедия)

При сборке можно задать пропорции относительно объёма Tier 1:

```yaml
assembly:
  mixing:
    base_tier: 1
    sources:
      books_ru:
        proportion: 0.8     # 80% от объёма tier 1
      wikipedia_ru:
        proportion: 0.3     # 30% от объёма tier 1
```

## Создание своего источника

1. Создайте файл в `sources/`, например `sources/my_dataset.py`:

```python
from core.source_base import BaseSource
from core.registry import register_source


@register_source
class MyDatasetSource(BaseSource):
    name = "my_dataset"
    quality_tier = 2
    content_type = "text"  # или "dialogue"

    def extract(self):
        # Генератор словарей в финальном формате
        yield {"lang": "ru", "text": "Пример текста..."}
        yield {"lang": "en", "text": "Example text..."}
```

2. Готово. `stepwise.py` найдёт его автоматически.

Формат записей:
- **dialogue**: `{"lang": str, "messages": [{"role": str, "content": str}, ...]}`
- **text**: `{"lang": str, "text": str}`

## Конфигурация

При первом запуске создаётся `config.yaml` с настройками по умолчанию. Основные секции:

- `logging` — уровни логирования, ротация
- `cache` — директория кеша
- `processing` — количество потоков
- `cleaners` — параметры очистки (языки, пороги)
- `sources` — включение/отключение источников
- `assembly` — настройки сборки

## Структура проекта

```
stepwise_alchemy/
├── stepwise.py              CLI и оркестрация
├── config.yaml              глобальная конфигурация
├── core/                    базовые классы и структуры
├── sources/                 источники данных
├── cleaners/                очистка и валидация текста
├── pipeline/                этапы пайплайна
├── data_io/                 работа с Parquet и метаданными
└── utils/                   логирование, конфиг
```

## Зависимости

- `pyarrow` — формат Parquet
- `datasets` — загрузка датасетов HuggingFace
- `transformers` — токенизация
- `tqdm` — прогресс-бары
- `pyyaml` — конфигурация