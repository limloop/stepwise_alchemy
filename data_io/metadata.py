"""
Чтение и запись metadata.json для источников.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.schemas import SourceMetadata, StageResult
from utils.logging_setup import get_logger

logger = get_logger("io.metadata")


def metadata_path(cache_root: str, source_name: str) -> Path:
    """Путь к metadata.json источника."""
    return Path(cache_root) / source_name / "metadata.json"


def load_metadata(cache_root: str, source_name: str) -> SourceMetadata:
    """Загружает метаданные источника. Если файла нет — возвращает пустые."""
    path = metadata_path(cache_root, source_name)

    if not path.exists():
        logger.debug("[%s] metadata.json не найден, создаю пустой", source_name)
        return SourceMetadata(source_name=source_name)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[%s] Ошибка чтения metadata.json: %s. Создаю пустой.", source_name, e)
        return SourceMetadata(source_name=source_name)

    raw = None
    if data.get("raw_extraction"):
        r = data["raw_extraction"]
        raw = StageResult(
            ok=r.get("ok", False),
            num_records=r.get("num_records", 0),
            duration_sec=r.get("duration_sec", 0.0),
            finished_at=r.get("finished_at", ""),
            languages=r.get("languages", []),
        )


    cleaning = None
    if data.get("cleaning"):
        c = data["cleaning"]
        cleaning = StageResult(
            ok=c.get("ok", False),
            num_records=c.get("num_records", 0),
            duration_sec=c.get("duration_sec", 0.0),
            finished_at=c.get("finished_at", ""),
            languages=r.get("languages", []),
        )

    return SourceMetadata(
        source_name=source_name,
        raw_extraction=raw,
        cleaning=cleaning,
    )


def save_metadata(cache_root: str, metadata: SourceMetadata) -> None:
    """Сохраняет метаданные источника."""
    path = metadata_path(cache_root, metadata.source_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {"source_name": metadata.source_name}

    if metadata.raw_extraction:
        data["raw_extraction"] = {
            "ok": metadata.raw_extraction.ok,
            "num_records": metadata.raw_extraction.num_records,
            "duration_sec": metadata.raw_extraction.duration_sec,
            "finished_at": metadata.raw_extraction.finished_at,
            "languages": metadata.raw_extraction.languages,
        }


    if metadata.cleaning:
        data["cleaning"] = {
            "ok": metadata.cleaning.ok,
            "num_records": metadata.cleaning.num_records,
            "duration_sec": metadata.cleaning.duration_sec,
            "finished_at": metadata.cleaning.finished_at,
            "languages": metadata.cleaning.languages,
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.debug("[%s] metadata.json сохранён", metadata.source_name)


def is_stage_done(cache_root: str, source_name: str, stage: str) -> bool:
    """
    Проверяет, завершён ли этап для источника.
    stage: "raw_extraction" или "cleaning"
    """
    # Проверяем наличие файла-результата
    if stage == "raw_extraction":
        result_file = Path(cache_root) / source_name / "raw.parquet"
    elif stage == "cleaning":
        result_file = Path(cache_root) / source_name / "cleaned.parquet"
    else:
        return False

    if not result_file.exists():
        return False

    # Проверяем метаданные
    metadata = load_metadata(cache_root, source_name)
    stage_result = getattr(metadata, stage, None)

    if stage_result is None or not stage_result.ok:
        return False

    return True