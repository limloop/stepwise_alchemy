"""
Этап 3 — Assembly: сборка финального датасета.
Режимы: chat (диалоги) и text (сплошной текст).
"""

import random
import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm
from transformers import AutoTokenizer

from core.registry import SourceRegistry
from core.schemas import AssemblyConfig
from data_io.parquet import read_parquet, write_parquet_streaming
from utils.logging_setup import get_logger

logger = get_logger("pipeline.assembly")


def _resolve_mixing(
    config: AssemblyConfig,
    registry: SourceRegistry,
    cache_root: str,
) -> dict:
    """
    Определяет итоговый объём записей для каждого источника согласно пропорциям из конфига.
    
    Returns:
        {source_name: max_records_to_take}  (None = все)
    """
    from data_io.parquet import count_rows

    # Собираем доступные источники из кеша (только cleaned)
    available = {}
    for name, source in registry.list_all().items():
        cleaned_path = Path(cache_root) / name / "cleaned.parquet"
        if cleaned_path.exists():
            available[name] = source

    if not available:
        logger.error("Нет очищенных источников. Запустите этап 2.")
        return {}

    # Разделяем по качеству
    tiers = {}
    for name, source in available.items():
        tier = source.quality_tier
        tiers.setdefault(tier, []).append(name)

    base_tier = config.base_tier
    if base_tier not in tiers:
        logger.warning("base_tier=%d не найден среди доступных (доступны: %s). Беру минимальный.",
                       base_tier, sorted(tiers.keys()))
        base_tier = min(tiers.keys())

    base_sources = tiers.get(base_tier, [])

    # Базовый объём — сумма всех записей tier=base_tier
    base_total = 0
    for name in base_sources:
        path = Path(cache_root) / name / "cleaned.parquet"
        base_total += count_rows(str(path))

    if base_total == 0:
        logger.error("Базовый объём (tier=%d) равен 0.", base_tier)
        return {}

    logger.info("Базовый объём (tier=%d): %d записей", base_tier, base_total)

    # Строим план
    plan = {}
    rules = {r.source_name: r for r in config.mixing_rules}

    for name, source in available.items():
        rule = rules.get(name)

        if rule and rule.use_all:
            plan[name] = None
            logger.info("[%s] use_all: взять все записи", name)
        elif rule and rule.proportion is not None:
            plan[name] = int(base_total * rule.proportion)
            logger.info("[%s] proportion=%.2f: %d записей", name, rule.proportion, plan[name])
        elif source.quality_tier == base_tier:
            plan[name] = None
            logger.info("[%s] tier=%d (базовый): взять все записи", name, base_tier)
        else:
            plan[name] = None
            logger.info("[%s] tier=%d: взять все записи (правило не задано)", name, source.quality_tier)

    return plan


def _load_records(
    source_name: str,
    cache_root: str,
    max_records: Optional[int],
) -> list:
    """Загружает записи из cleaned.parquet, опционально ограничивая количество."""
    path = Path(cache_root) / source_name / "cleaned.parquet"
    records = list(read_parquet(str(path)))

    if max_records is not None and len(records) > max_records:
        records = random.sample(records, max_records)

    return records


def _assemble_chat_mode(
    config: AssemblyConfig,
    registry: SourceRegistry,
    plan: dict,
    cache_root: str,
) -> None:
    """Сборка в режиме chat (диалоги)."""
    logger.info("=" * 50)
    logger.info("Режим: chat (диалоги)")

    tokenizer = AutoTokenizer.from_pretrained(config.tokenizer_name)

    # Собираем все диалоги
    all_dialogs = []
    for name, max_records in plan.items():
        source = registry.get(name)
        if source is None or source.content_type != "dialogue":
            logger.debug("[%s] Пропущен: content_type != dialogue", name)
            continue

        records = _load_records(name, cache_root, max_records)
        logger.info("[%s] Загружено %d диалогов", name, len(records))
        all_dialogs.extend(records)

    if config.shuffle:
        random.seed(config.seed)
        random.shuffle(all_dialogs)

    logger.info("Всего диалогов: %d", len(all_dialogs))

    # Фильтрация по длине и минимальному числу сообщений
    filtered = []
    for dialog in tqdm(all_dialogs, desc="Фильтрация диалогов"):
        messages = dialog.get("messages", [])
        if len(messages) < config.chat_min_messages:
            continue

        # Подсчёт токенов
        try:
            if config.chat_apply_chat_template:
                tokens = tokenizer.apply_chat_template(
                    messages,
                    return_tensors="pt",
                    truncation=True,
                    max_length=config.chat_max_tokens,
                )
                token_count = tokens.shape[-1]
            else:
                # Примерный подсчёт: конкатенируем все content
                text = " ".join(m.get("content", "") for m in messages)
                token_count = len(tokenizer.encode(text))
        except Exception as e:
            logger.debug("Ошибка токенизации диалога: %s", e)
            continue

        if token_count > config.chat_max_tokens:
            logger.debug("Диалог отброшен: %d токенов > %d", token_count, config.chat_max_tokens)
            continue

        filtered.append({
            "lang": dialog.get("lang", "unknown"),
            "messages": messages,
            "token_count": token_count,
        })

    logger.info("После фильтрации: %d диалогов", len(filtered))

    # Сохраняем как есть (без нарезки — диалоги нарезать не надо)
    output_path = Path(config.output_dir) / "chat"
    output_path.mkdir(parents=True, exist_ok=True)

    write_parquet_streaming(
        ({"lang": d["lang"], "messages": d["messages"]} for d in filtered),
        str(output_path / "dialogues.parquet"),
    )

    logger.info("Сохранено в %s", output_path / "dialogues.parquet")


def _assemble_text_mode(
    config: AssemblyConfig,
    registry: SourceRegistry,
    plan: dict,
    cache_root: str,
) -> None:
    """Сборка в режиме text (сплошной текст) с нарезкой по токенам."""
    logger.info("=" * 50)
    logger.info("Режим: text (сплошной текст)")

    tokenizer = AutoTokenizer.from_pretrained(config.tokenizer_name)

    # Собираем все тексты
    all_texts = []
    for name, max_records in plan.items():
        source = registry.get(name)
        if source is None or source.content_type != "text":
            logger.debug("[%s] Пропущен: content_type != text", name)
            continue

        records = _load_records(name, cache_root, max_records)
        logger.info("[%s] Загружено %d текстов", name, len(records))
        all_texts.extend(records)

    if config.shuffle:
        random.seed(config.seed)
        random.shuffle(all_texts)

    logger.info("Всего текстов: %d", len(all_texts))

    total_tokens_written = 0

    for chunk_size in config.text_chunk_sizes:
        logger.info("Нарезка чанков по %d токенов...", chunk_size)

        output_path = Path(config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / f"text/chunks_{chunk_size}.parquet"
        chunks = []

        for record in tqdm(all_texts, desc=f"chunk_{chunk_size}"):
            if config.max_total_tokens and total_tokens_written >= config.max_total_tokens:
                break

            text = record.get("text", "")
            lang = record.get("lang", "unknown")

            tokens = tokenizer.encode(text)
            if len(tokens) < config.text_min_tokens:
                continue

            # Обрезаем слишком длинные тексты
            if len(tokens) > 32768:
                tokens = tokens[:32768]

            for i in range(0, len(tokens), config.text_stride):
                if config.max_total_tokens and total_tokens_written >= config.max_total_tokens:
                    break

                chunk_tokens = tokens[i:i + chunk_size]
                if len(chunk_tokens) < config.text_min_tokens:
                    continue

                chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
                chunks.append({
                    "lang": lang,
                    "text": chunk_text,
                    "token_count": len(chunk_tokens),
                })

                total_tokens_written += len(chunk_tokens)

        # Запись одним файлом
        if chunks:
            write_parquet_streaming(iter(chunks), str(output_file))
            logger.info("Чанки %d токенов: %d записей → %s",
                        chunk_size, len(chunks), output_file)
        else:
            logger.warning("Чанки %d токенов: нет данных", chunk_size)

    logger.info("Всего токенов записано: %d", total_tokens_written)


def run_assembly_stage(
    sources: list[str],
    registry: SourceRegistry,
    config: dict,
    modes: set,
) -> None:
    """
    Этап 3: Assembly — сборка финального датасета.
    """
    cache_root = config.get("cache", {}).get("root", "cache")
    assembly_cfg = config.get("assembly", {})

    if not assembly_cfg:
        logger.error("Секция 'assembly' отсутствует в конфиге.")
        return

    # Парсим конфиг сборки через from_dict
    asm_config = AssemblyConfig.from_dict(assembly_cfg)

    logger.info("=" * 50)
    logger.info("Этап 3: Assembly — сборка финального датасета")
    logger.info("Режимы: %s", modes)
    logger.info("Источников: %d", len(sources))
    logger.info("Выходная директория: %s", asm_config.output_dir)
    logger.debug("Правила смешивания: %s", asm_config.mixing_rules)

    # Определяем план смешивания
    plan = _resolve_mixing(asm_config, registry, cache_root)

    if not plan:
        logger.error("Не удалось построить план смешивания.")
        return

    start_time = time.time()

    if "chat" in modes:
        _assemble_chat_mode(asm_config, registry, plan, cache_root)

    if "text" in modes:
        _assemble_text_mode(asm_config, registry, plan, cache_root)

    duration = time.time() - start_time
    logger.info("Этап 3 завершён за %.1f сек", duration)