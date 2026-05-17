"""
Этап 2 — Clean: очистка и валидация данных.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
import pyarrow as pa
import pyarrow.parquet as pq

from tqdm import tqdm

from core.registry import SourceRegistry
from core.schemas import StageResult
from data_io.metadata import load_metadata, save_metadata, is_stage_done
from data_io.parquet import read_parquet, write_parquet_batch, count_rows, create_parquet_writer
from cleaners.text_cleaner import clean_text
from cleaners.validators import is_valid_text, contains_python_code
from utils.logging_setup import get_logger

logger = get_logger("pipeline.clean")


def clean_record(record, source, config):
    cleaners = config.get("cleaners", {})
    remove_python = cleaners.get("remove_python_code", True)
    allowed_langs = set(cleaners.get("allowed_langs", ["ru", "en"]))

    lang = record.get("lang", "unknown")

    if lang not in allowed_langs:
        return None

    if source.content_type == "dialogue":
        msgs = record.get("messages", [])

        for msg in msgs:
            t = msg.get("content", "")

            if not t:
                continue

            if remove_python and contains_python_code(t):
                return None

            t = clean_text(t)

            if not is_valid_text(t):
                return None

            msg["content"] = t

        return {"lang": lang, "messages": msgs}

    else:
        t = record.get("text", "")

        if not t:
            return None

        if remove_python and contains_python_code(t):
            return None

        t = clean_text(t)

        if not is_valid_text(t):
            return None

        return {"lang": lang, "text": t}

def process_batch(args):
    batch, source_dict, config = args

    out = []

    for record in batch:
        cleaned = clean_record(record, source_dict, config)
        if cleaned:
            out.append(cleaned)

    return out, len(batch)

def _clean_single_source(source_name, registry, config):

    cache_root = config.get("cache", {}).get("root", "cache")

    source = registry.get(source_name)
    if not source:
        return source_name, False, 0, 0

    raw_path = Path(cache_root) / source_name / "raw.parquet"
    out_path = Path(cache_root) / source_name / "cleaned.parquet"

    parquet = pq.ParquetFile(raw_path)

    workers = config.get("processing", {}).get("max_workers", 4)
    MAX_IN_FLIGHT = workers * 2

    writer = None
    buffer = []

    num_in = 0
    num_out = 0
    langs = set()
    start_time = time.time()

    futures = deque()

    with ProcessPoolExecutor(max_workers=workers) as executor:

        def submit(batch):
            rows = pa.Table.from_batches([batch]).to_pylist()
            return executor.submit(process_batch, (rows, source, config)), len(rows)

        batch_iter = parquet.iter_batches(batch_size=5000)

        # initial fill
        for _ in range(MAX_IN_FLIGHT):
            try:
                batch = next(batch_iter)
            except StopIteration:
                break

            fut, n = submit(batch)
            futures.append((fut, n))

        with tqdm(total=count_rows(str(raw_path)), desc=source_name, unit="rows") as pbar:

            while futures:

                fut, n_in = futures.popleft()

                cleaned_batch, _ = fut.result()

                num_in += n_in

                if cleaned_batch:

                    if writer is None:
                        writer = create_parquet_writer(str(out_path), cleaned_batch[0])

                    buffer.extend(cleaned_batch)
                    num_out += len(cleaned_batch)

                    for r in cleaned_batch:
                        langs.add(r["lang"])

                    if len(buffer) >= 5000:
                        write_parquet_batch(writer, buffer)
                        buffer.clear()

                pbar.update(n_in)

                # refill pipeline
                try:
                    batch = next(batch_iter)
                    fut_new, n_new = submit(batch)
                    futures.append((fut_new, n_new))

                except StopIteration:
                    continue

    if buffer and writer:
        write_parquet_batch(writer, buffer)

    if writer:
        writer.close()

    meta = load_metadata(cache_root, source_name)

    meta.cleaning = StageResult(
        ok=True,
        num_records=num_out,
        duration_sec=round(time.time() - start_time, 2),
        finished_at=datetime.now(timezone.utc).isoformat(),
        languages=sorted(langs),
    )

    save_metadata(cache_root, meta)

    return source_name, True, num_in, num_out


def run_clean_stage(
    sources: list[str],
    registry: SourceRegistry,
    config: dict,
) -> dict:
    """
    Этап 2: Clean — последовательная очистка и валидация данных.
    """
    cache_root = config.get("cache", {}).get("root", "cache")
    force = config.get("force", False)

    logger.info("=" * 50)
    logger.info("Этап 2: Clean — очистка и валидация")
    logger.info("Источников всего: %d", len(sources))
    logger.info("Force: %s", force)
    logger.debug(
        "Параметры очистки: %s",
        config.get("cleaners", {}),
    )

    pending = []
    skipped = []

    for name in sources:
        raw_path = Path(cache_root) / name / "raw.parquet"

        if not raw_path.exists():
            logger.warning(
                "[%s] raw.parquet не найден, пропущен. "
                "Запустите этап 1.",
                name,
            )
            continue

        if not force and is_stage_done(
            cache_root,
            name,
            "cleaning",
        ):
            metadata = load_metadata(cache_root, name)

            existing = (
                metadata.cleaning.num_records
                if metadata.cleaning
                else 0
            )

            skipped.append((name, existing))

        else:
            pending.append(name)

    if skipped:
        logger.info(
            "Пропущено (уже очищено): %d источников",
            len(skipped),
        )

        for name, count in skipped:
            logger.info(
                "  [%s] %d записей в кеше",
                name,
                count,
            )

    if not pending:
        logger.info("Нет источников для очистки.")
        return {}

    logger.info(
        "Источников к очистке: %d",
        len(pending),
    )

    results = {}

    with tqdm(
        total=len(pending),
        desc="Источники",
        unit="src",
    ) as overall_pbar:

        for name in pending:
            try:
                (
                    source_name,
                    success,
                    num_input,
                    num_output,
                ) = _clean_single_source(
                    name,
                    registry,
                    config,
                )

                if success:
                    results[source_name] = {
                        "input": num_input,
                        "output": num_output,
                    }

            except Exception as e:
                logger.error(
                    "[%s] Ошибка при обработке источника: %s",
                    name,
                    e,
                    exc_info=True,
                )

            overall_pbar.update(1)

    logger.info(
        "Этап 2 завершён: успешно %d/%d источников",
        len(results),
        len(pending),
    )

    return results