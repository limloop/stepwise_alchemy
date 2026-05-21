"""
Чтение и запись Parquet-файлов.
"""

import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Iterator, List

from utils.logging_setup import get_logger

logger = get_logger("io.parquet")


def infer_arrow_type(value):
    """
    Рекурсивное определение Arrow-типа.
    """

    if isinstance(value, str):
        return pa.string()

    if isinstance(value, bool):
        return pa.bool_()

    if isinstance(value, int):
        return pa.int64()

    if isinstance(value, float):
        return pa.float64()

    if isinstance(value, list):

        if not value:
            return pa.list_(pa.string())

        first = value[0]

        # list[dict]
        if isinstance(first, dict):
            fields = [
                pa.field(k, infer_arrow_type(v))
                for k, v in first.items()
            ]
            return pa.list_(pa.struct(fields))

        return pa.list_(infer_arrow_type(first))

    if isinstance(value, dict):
        fields = [
            pa.field(k, infer_arrow_type(v))
            for k, v in value.items()
        ]
        return pa.struct(fields)

    return pa.string()

def infer_schema(record: dict) -> pa.Schema:
    """
    Автоопределение схемы по первой записи.
    """

    fields = [
        pa.field(key, infer_arrow_type(value))
        for key, value in record.items()
    ]

    return pa.schema(fields)

def write_parquet_streaming(
    records: Iterator[dict],
    output_path: str,
    batch_size: int = 10000,
) -> int:
    """
    Потоковая запись parquet с автоопределением schema.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    iterator = iter(records)

    try:
        first_record = next(iterator)
    except StopIteration:
        return 0

    schema = infer_schema(first_record)

    writer = pq.ParquetWriter(
        output_path,
        schema,
        compression="zstd",
    )

    total = 0
    batch = [first_record]

    try:

        for record in iterator:

            batch.append(record)

            if len(batch) >= batch_size:

                table = pa.Table.from_pylist(
                    batch,
                    schema=schema,
                )

                writer.write_table(table)

                total += len(batch)

                batch.clear()

        if batch:

            table = pa.Table.from_pylist(
                batch,
                schema=schema,
            )

            writer.write_table(table)

            total += len(batch)

    finally:
        writer.close()

    return total

def write_parquet_batch(
    writer: pq.ParquetWriter,
    records: list[dict],
) -> int:
    """
    Записывает батч записей в существующий ParquetWriter.

    Returns:
        Количество записанных строк.
    """

    if not records:
        return 0

    table = pa.Table.from_pylist(
        records,
        schema=writer.schema,
    )

    writer.write_table(table)

    return len(records)

def read_parquet(
    input_path: str,
    batch_size: int = 10000,
) -> Iterator[dict]:
    """
    Потоковое чтение parquet без загрузки файла целиком в RAM.
    """

    path = Path(input_path)

    if not path.exists():
        logger.error("Файл не найден: %s", input_path)
        return

    parquet_file = pq.ParquetFile(input_path)

    for batch in parquet_file.iter_batches(batch_size=batch_size):
        table = pa.Table.from_batches([batch])

        for row in table.to_pylist():
            yield row

def read_parquet_full(input_path: str) -> List[dict]:
    """
    Чтение parquet целиком в ram.
    """

    try:
        table = pq.read_table(input_path)
        result = table.to_pylist()
        
        return result
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл не найден: {input_path}")
    except Exception as e:
        raise Exception(f"Ошибка при чтении Parquet файла: {str(e)}")

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

def create_parquet_writer(
    output_path: str,
    example_record: dict,
    compression: str = "zstd",
) -> pq.ParquetWriter:
    """
    Создаёт ParquetWriter на основе примерной записи.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = infer_schema(example_record)

    return pq.ParquetWriter(
        output_path,
        schema=schema,
        compression=compression,
    )