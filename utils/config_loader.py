"""
Загрузка и валидация конфигурации StepWise Alchemy.
При отсутствии config.yaml создаёт его с настройками по умолчанию.
"""

from pathlib import Path
from typing import Any, Dict

import yaml

from utils.logging_setup import get_logger

logger = get_logger("config")

# Конфиг по умолчанию
DEFAULT_CONFIG = {
    "logging": {
        "log_dir": "logs",
        "log_level": "INFO",
        "console_level": "INFO",
        "file_level": "DEBUG",
        "max_bytes": 10485760,  # 10 MB
        "backup_count": 5,
    },
    "cache": {
        "root": "cache",
    },
    "processing": {
        "max_workers": 4,
    },
    "cleaners": {
        "remove_python_code": True,
        "garbage_threshold": 0.7,
        "allowed_langs": ["ru", "en"],
    },
    "sources": {
        "test_dialogue": {
            "enabled": True,
        },
        "test_text": {
            "enabled": True,
            "quality_tier_override": 2,
        },
    },
    "assembly": {
        "output_dir": "output",

        "seed": 42,

        "shuffle": {
            "enabled": True,
            "global_shuffle": True,
            "index_file": "shuffle.idx",
        },
        "chunking": {
            # target chunk size
            "target_tokens": 512,

            # overlap
            "stride_tokens": 448,

            # approximate tokenizer heuristic
            "chars_per_token": 3.0,

            # per-language overrides
            "chars_per_token_by_lang": {},

            # safety multiplier
            "safety_margin": 1.15,

            # hard limits
            "min_chunk_chars": 100,
            "max_chunk_chars": 32000,

            # limit chunks from one source text
            "max_chunks_per_document": 24,

            # boundary refinement
            "boundary_refinement": {
                "enabled": True,
                "tokenizer": "microsoft/Phi-3.5-mini-instruct",
                "max_refinement_tokens": 1024,
            },
        },
        "cache_build": {
            # temporary chunk cache
            "enabled": True,

            # shard size
            "target_shard_size_mb": 1024,

            # rewrite final dataset
            "rewrite_final_dataset": True,

            # remove temporary cache
            "cleanup_after_finalize": True,
        },
        "storage": {
            # "text" | "tokens" | "both"
            "format": "text",

            # save token ids
            "store_token_ids": False,

            # save original text
            "store_text": True,

            # compression
            "compression": "zstd",
        },
        "mixing": {
            "base_tier": 1,

            "sources": {}
        },
        "output": {

            # final shard size
            "target_shard_size_mb": 1024,

            # parquet row group size
            "row_group_size": 10000,
        },
    }
}


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Рекурсивно сливает override в base.
    Значения из override имеют приоритет.
    Корректно обрабатывает случай, когда override меняет тип значения
    (например, null вместо dict).
    """
    result = base.copy()
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def create_default_config(config_path: str) -> dict:
    """Создаёт config.yaml с настройками по умолчанию."""
    path = Path(config_path)

    # Создаём директорию, если нужно
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            DEFAULT_CONFIG,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    logger.info("Создан новый config.yaml с настройками по умолчанию: %s", path)
    return DEFAULT_CONFIG.copy()


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Загружает конфигурацию из YAML-файла.
    Если файл отсутствует или пуст — создаёт его с дефолтными значениями.
    CLI-аргументы применяются отдельно в stepwise.py поверх результата.
    """
    path = Path(config_path)

    # Файла нет — создаём
    if not path.exists():
        logger.warning("config.yaml не найден, создаю с настройками по умолчанию")
        return create_default_config(config_path)

    # Файл есть, но пустой — перезаписываем дефолтным
    if path.stat().st_size == 0:
        logger.warning("config.yaml пуст, заполняю настройками по умолчанию")
        return create_default_config(config_path)

    # Читаем файл
    try:
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(
            "Ошибка парсинга config.yaml: %s. Использую значения по умолчанию.", e
        )
        return DEFAULT_CONFIG.copy()

    if user_config is None:
        logger.warning(
            "config.yaml пуст (None после парсинга), использую значения по умолчанию"
        )
        return create_default_config(config_path)

    if not isinstance(user_config, dict):
        logger.error(
            "config.yaml должен быть словарём, а не %s. Использую значения по умолчанию.",
            type(user_config).__name__,
        )
        return DEFAULT_CONFIG.copy()

    # Сливаем пользовательский конфиг с дефолтным (дефолт — база, пользователь — поверх)
    merged = _deep_merge(DEFAULT_CONFIG, user_config)
    logger.info("Конфигурация загружена из %s", config_path)
    logger.debug("Итоговый конфиг: %s", merged)

    return merged


def get_cache_root(config: dict) -> str:
    """Извлекает путь к корневой директории кеша из конфига."""
    return config.get("cache", {}).get("root", "cache")


def get_logging_config(config: dict) -> dict:
    """Извлекает настройки логирования из конфига."""
    return config.get("logging", DEFAULT_CONFIG["logging"])


def get_cleaners_config(config: dict) -> dict:
    """Извлекает настройки очистки из конфига."""
    return config.get("cleaners", DEFAULT_CONFIG["cleaners"])


def get_sources_config(config: dict) -> dict:
    """Извлекает настройки источников из конфига."""
    return config.get("sources", {})


def get_assembly_config(config: dict) -> dict:
    """Извлекает настройки сборки из конфига."""
    return config.get("assembly", DEFAULT_CONFIG["assembly"])