"""
Этап 2 — Clean: очистка и валидация данных.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from core.registry import SourceRegistry
from core.schemas import SourceMetadata, StageResult
from data_io.metadata import load_metadata, save_metadata, is_stage_done
from data_io.parquet import read_parquet, write_parquet, count_rows
from cleaners.text_cleaner import clean_text
from cleaners.validators import is_valid_text, contains_python_code
from utils.logging_setup import get_logger

logger = get_logger("pipeline.clean")


def _clean_single_source(
    source_name: str,
    registry: SourceRegistry,
    config: dict,
    pbar: tqdm | None = None,
) -> tuple[str, bool, int, int]:
    """
    Очищает данные одного источника.
    Выполняется в отдельном потоке.

    Returns:
        (source_name, success, num_input, num_output)
    """
    cache_root = config.get("cache_root", "cache")
    cleaners_config = config.get("cleaners", {})

    remove_python = cleaners_config.get("remove_python_code", True)
    allowed_langs = cleaners_config.get("allowed_langs", ["ru", "en"])

    source = registry.get(source_name)
    if source is None:
        logger.error("[%s] Источник не найден в реестре", source_name)
        return source_name, False, 0, 0

    raw_path = str(Path(cache_root) / source_name / "raw.parquet")
    cleaned_path = str(Path(cache_root) / source_name / "cleaned.parquet")

    logger.info("[%s] Начало очистки...", source_name)
    start_time = time.time()

    num_input = 0
    num_output = 0

    def generate_cleaned():
        nonlocal num_input, num_output

        for record in read_parquet(raw_path):
            num_input += 1

            # Запись уже в формате {"lang": ..., "messages": ...} или {"lang": ..., "text": ...}

            texts_to_clean = []

            if source.content_type == "dialogue":
                messages = record.get("messages", [])
                for msg in messages:
                    texts_to_clean.append(msg)  # словарь с ключом "content"
            elif source.content_type == "text":
                texts_to_clean.append(record)  # словарь с ключом "text"

            # Очистка каждого текстового поля
            valid = True
            for item in texts_to_clean:
                # Определяем ключ поля
                field = "content" if source.content_type == "dialogue" else "text"
                content = item.get(field, "")

                # Проверка на Python-код
                if remove_python and contains_python_code(content):
                    logger.debug("[%s] Запись отбракована: найден Python-код", source_name)
                    valid = False
                    break

                # Проверка на валидность языка
                if not is_valid_text(content):
                    logger.debug("[%s] Запись отбракована: невалидный текст", source_name)
                    valid = False
                    break

                # Очистка
                cleaned = clean_text(content)
                if not cleaned:
                    logger.debug("[%s] Запись отбракована: после очистки пусто", source_name)
                    valid = False
                    break

                item[field] = cleaned

            if not valid:
                if pbar:
                    pbar.update(1)
                continue

            # Языковой фильтр
            lang = record.get("lang", "unknown")
            if lang not in allowed_langs:
                logger.debug("[%s] Запись отбракована: язык '%s' не разрешён", source_name, lang)
                if pbar:
                    pbar.update(1)
                continue

            if source.content_type == "dialogue":
                yield {"lang": lang, "messages": record["messages"]}
            elif source.content_type == "text":
                yield {"lang": lang, "text": record["text"]}

            num_output += 1
            if pbar:
                pbar.update(1)

    try:
        written = write_parquet(generate_cleaned(), cleaned_path)
        duration = time.time() - start_time

        metadata = load_metadata(cache_root, source_name)
        metadata.cleaning = StageResult(
            ok=True,
            num_records=num_output,
            duration_sec=round(duration, 2),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        save_metadata(cache_root, metadata)

        logger.info(
            "[%s] Завершено: %d -> %d записей за %.1f сек (отсев %.1f%%)",
            source_name,
            num_input,
            num_output,
            duration,
            (1 - num_output / max(num_input, 1)) * 100,
        )
        return source_name, True, num_input, num_output

    except Exception as e:
        logger.error("[%s] Ошибка при очистке: %s", source_name, e, exc_info=True)

        metadata = load_metadata(cache_root, source_name)
        metadata.cleaning = StageResult(ok=False)
        save_metadata(cache_root, metadata)

        return source_name, False, num_input, num_output


def run_clean_stage(
    sources: list[str],
    registry: SourceRegistry,
    config: dict,
) -> dict:
    """
    Этап 2: Clean — параллельная очистка и валидация данных.
    """
    cache_root = config.get("cache_root", "cache")
    max_workers = config.get("max_workers", 4)
    force = config.get("force", False)

    logger.info("=" * 50)
    logger.info("Этап 2: Clean — очистка и валидация")
    logger.info("Источников всего: %d", len(sources))
    logger.info("Max workers: %d", max_workers)
    logger.info("Force: %s", force)
    logger.debug("Параметры очистки: %s", config.get("cleaners", {}))

    # Фильтруем: оставляем только те, что ещё не очищены и имеют raw.parquet
    pending = []
    skipped = []
    for name in sources:
        raw_path = Path(cache_root) / name / "raw.parquet"
        if not raw_path.exists():
            logger.warning("[%s] raw.parquet не найден, пропущен. Запустите этап 1.", name)
            continue

        if not force and is_stage_done(cache_root, name, "cleaning"):
            metadata = load_metadata(cache_root, name)
            existing = metadata.cleaning.num_records if metadata.cleaning else 0
            skipped.append((name, existing))
        else:
            pending.append(name)

    if skipped:
        logger.info("Пропущено (уже очищено): %d источников", len(skipped))
        for name, count in skipped:
            logger.info("  [%s] %d записей в кеше", name, count)

    if not pending:
        logger.info("Нет источников для очистки.")
        return {}

    # Суммируем общее количество строк для прогресс-бара
    total_rows = sum(
        count_rows(str(Path(cache_root) / name / "raw.parquet"))
        for name in pending
    )
    logger.info("Источников к очистке: %d, всего записей: %d", len(pending), total_rows)

    results = {}

    with tqdm(total=total_rows, desc="Очистка", unit="записей") as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _clean_single_source, name, registry, config, pbar
                ): name
                for name in pending
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    source_name, success, num_input, num_output = future.result()
                    if success:
                        results[source_name] = {"input": num_input, "output": num_output}
                except Exception as e:
                    logger.error(
                        "[%s] Неожиданная ошибка в потоке: %s", name, e, exc_info=True
                    )

    logger.info(
        "Этап 2 завершён: успешно %d/%d источников",
        len(results),
        len(pending),
    )

    return results