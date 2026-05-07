"""
Чтение и запись Parquet-файлов.
"""

import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Iterator

from utils.logging_setup import get_logger

logger = get_logger("io.parquet")


def write_parquet(records: Iterator[dict], output_path: str) -> int:
    """
    Записывает словари в Parquet-файл.
    Автоматически определяет схему по первой записи.

    Args:
        records: итератор словарей
        output_path: путь к .parquet файлу

    Returns:
        Количество записанных записей
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Собираем все записи в список (Parquet требует знать схему заранее)
    # Для очень больших датасетов можно писать батчами, но пока так
    batches = []
    count = 0

    for record in records:
        batches.append(record)
        count += 1

    if not batches:
        logger.warning("Нет записей для записи в %s", output_path)
        return 0

    table = pa.Table.from_pylist(batches)
    pq.write_table(table, output_path, compression="snappy")

    file_size_mb = path.stat().st_size / (1024 * 1024)
    logger.debug("Записано %d записей в %s (%.2f MB)", count, output_path, file_size_mb)

    return count


def read_parquet(input_path: str) -> Iterator[dict]:
    """
    Читает Parquet-файл построчно.
    """
    path = Path(input_path)
    if not path.exists():
        logger.error("Файл не найден: %s", input_path)
        return

    table = pq.read_table(input_path)
    for batch in table.to_batches(max_chunksize=1000):
        for row in batch.to_pylist():
            yield row


def count_rows(parquet_path: str) -> int:
    """Возвращает количество строк в Parquet-файле."""
    path = Path(parquet_path)
    if not path.exists():
        return 0
    try:
        table = pq.read_metadata(parquet_path)
        return table.num_rows
    except Exception as e:
        logger.warning("Не удалось прочитать метаданные %s: %s", parquet_path, e)
        return 0