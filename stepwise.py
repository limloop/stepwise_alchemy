#!/usr/bin/env python3
"""
StepWise Alchemy — модульный пайплайн загрузки и очистки данных.
"""

import argparse
import sys

from core.registry import load_registry, resolve_sources
from pipeline.extractor import run_extract_stage
from pipeline.cleaner import run_clean_stage
from pipeline.assembler import run_assembly_stage
from utils.logging_setup import setup_logging, get_logger
from utils.config_loader import load_config


def parse_stages(stage_arg: str) -> set:
    """Разбор аргумента --stage в набор номеров этапов."""
    logger = get_logger("cli")
    stages = set()
    for part in stage_arg.split(","):
        part = part.strip()
        if part in ("1", "2", "3"):
            stages.add(int(part))
        elif part.lower() == "all":
            logger.debug("Запрошены все этапы (all)")
            return {1, 2, 3}
        else:
            logger.warning("Неизвестный номер этапа: '%s', пропущен", part)
    logger.debug("Этапы к выполнению: %s", sorted(stages))
    return stages


def parse_args() -> argparse.Namespace:
    """CLI аргументы."""
    parser = argparse.ArgumentParser(
        prog="stepwise",
        description="StepWise Alchemy — пайплайн загрузки и очистки данных",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="1,2,3",
        help="Этапы для выполнения: 1, 2, 3 или all (по умолчанию: 1,2,3)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="chat,text",
        help="Режимы сборки для stage 3: chat, text (по умолчанию: chat,text)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Обработать только указанный источник (по умолчанию: все активные)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительно перезаписать существующие результаты этапов",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Путь к файлу конфигурации (по умолчанию: config.yaml)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Количество параллельных воркеров (по умолчанию из конфига)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Уровень логирования (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Загружаем конфиг (создастся, если нет)
    config = load_config(args.config)

    # --- Логирование ---
    log_config = config.get("logging", {})
    log_level = args.log_level or log_config.get("log_level", "INFO")

    setup_logging(
        log_dir=log_config.get("log_dir", "logs"),
        log_level=log_level,
        console_level=log_config.get("console_level", "INFO"),
        file_level=log_config.get("file_level", "DEBUG"),
        max_bytes=log_config.get("max_bytes", 10 * 1024 * 1024),
        backup_count=log_config.get("backup_count", 5),
    )

    logger = get_logger("main")
    logger.info("StepWise Alchemy starting")
    logger.debug("CLI args: %s", vars(args))

    # --- Переопределение из CLI ---
    if args.max_workers is not None:
        config["processing"]["max_workers"] = args.max_workers
        logger.debug("max_workers переопределён: %d", args.max_workers)

    if args.force:
        config["force"] = True
        logger.warning("Флаг --force: существующие результаты будут перезаписаны")
    else:
        config["force"] = False

    # --- Реестр источников ---
    registry = load_registry()

    # --- Разрешение источников ---
    sources = resolve_sources(
        registry,
        cli_source=args.source,
        config_sources=config.get("sources", {}),
    )

    if not sources:
        logger.error("Нет доступных источников. Проверьте:")
        logger.error("  - наличие модулей в sources/")
        logger.error("  - настройки в config.yaml (секция sources)")
        logger.error("  - правильность имени в --source")
        sys.exit(1)

    # --- Определение этапов ---
    stages = parse_stages(args.stage)
    logger.debug("Этапы к выполнению: %s", sorted(stages))

    # --- Выполнение ---
    try:
        if 1 in stages:
            run_extract_stage(sources, registry, config)

        if 2 in stages:
            run_clean_stage(sources, registry, config)

        if 3 in stages:
            modes = set()
            for m in args.mode.split(","):
                m = m.strip()
                if m in ("chat", "text"):
                    modes.add(m)
            if not modes:
                modes = {"chat", "text"}
            run_assembly_stage(sources, registry, config, modes)

    except KeyboardInterrupt:
        logger.warning("Прервано пользователем (Ctrl+C)")
        sys.exit(130)

    except Exception as e:
        logger.critical("Критическая ошибка: %s", e, exc_info=True)
        sys.exit(1)

    logger.info("StepWise Alchemy завершён успешно.")


if __name__ == "__main__":
    main()