"""
Этап 1 — Extract: загрузка сырых данных из источников.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from core.registry import SourceRegistry
from core.schemas import SourceMetadata, StageResult
from data_io.metadata import load_metadata, save_metadata, is_stage_done
from data_io.parquet import write_parquet_streaming, count_rows
from utils.logging_setup import get_logger

logger = get_logger("pipeline.extract")


def _extract_single_source(
    source_name: str,
    registry: SourceRegistry,
    cache_root: str,
    force: bool = False,
) -> tuple[str, bool, int]:
    """
    Потоковая загрузка одного источника.
    """

    source = registry.get(source_name)

    if source is None:
        logger.error("[%s] Источник не найден", source_name)
        return source_name, False, 0

    logger.info("[%s] Начало загрузки...", source_name)

    start_time = time.time()

    try:
        raw_path = Path(cache_root) / source_name / "raw.parquet"
        raw_path.parent.mkdir(parents=True, exist_ok=True)

        langs_set = set()

        def tracked_generator():
            for record in source.extract():

                lang = record.get("lang")

                if lang:
                    langs_set.add(lang)

                yield record

        num_records = write_parquet_streaming(
            tracked_generator(),
            str(raw_path),
        )

        duration = time.time() - start_time

        metadata = load_metadata(cache_root, source_name)

        metadata.raw_extraction = StageResult(
            ok=True,
            num_records=num_records,
            duration_sec=round(duration, 2),
            finished_at=datetime.now(timezone.utc).isoformat(),
            languages=sorted(langs_set) if langs_set else None,
        )

        save_metadata(cache_root, metadata)

        logger.info(
            "[%s] Завершено: %d записей за %.1f сек",
            source_name,
            num_records,
            duration,
        )

        return source_name, True, num_records

    except Exception as e:
        logger.error(
            "[%s] Ошибка загрузки: %s",
            source_name,
            e,
            exc_info=True,
        )

        metadata = load_metadata(cache_root, source_name)
        metadata.raw_extraction = StageResult(ok=False)
        save_metadata(cache_root, metadata)

        return source_name, False, 0


def run_extract_stage(
    sources: list[str],
    registry: SourceRegistry,
    config: dict,
) -> dict:
    """
    Этап 1: Extract — последовательная загрузка сырых данных.

    Args:
        sources: список имён источников
        registry: реестр источников
        config: глобальный конфиг

    Returns:
        Словарь {source_name: num_records} для успешно загруженных
    """
    cache_root = config.get("cache", {}).get("root", "cache")
    force = config.get("force", False)

    logger.info("=" * 50)
    logger.info("Этап 1: Extract — загрузка сырых данных")
    logger.info("Источников всего: %d", len(sources))
    logger.info("Force: %s", force)

    # Фильтруем: оставляем только те, что ещё не загружены
    pending = []
    skipped = []

    for name in sources:
        if not force and is_stage_done(cache_root, name, "raw_extraction"):
            metadata = load_metadata(cache_root, name)
            existing = (
                metadata.raw_extraction.num_records
                if metadata.raw_extraction
                else 0
            )
            skipped.append((name, existing))
        else:
            pending.append(name)

    if skipped:
        logger.info("Пропущено (уже загружено): %d источников", len(skipped))
        for name, count in skipped:
            logger.info("  [%s] %d записей в кеше", name, count)

    if not pending:
        logger.info("Нет источников для загрузки.")
        return {}

    logger.info("Источников к загрузке: %d", len(pending))

    results = {}

    for name in pending:
        try:
            source_name, success, num_records = _extract_single_source(
                name,
                registry,
                cache_root,
                force,
            )

            if success:
                results[source_name] = num_records

        except Exception as e:
            logger.error(
                "[%s] Ошибка при загрузке источника: %s",
                name,
                e,
                exc_info=True,
            )

    logger.info(
        "Этап 1 завершён: успешно %d/%d источников",
        len(results),
        len(pending),
    )

    return results