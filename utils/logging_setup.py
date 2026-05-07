"""
Настройка логирования для StepWise Alchemy.
Обеспечивает одновременный вывод в консоль и файл,
с ротацией, отдельным файлом на каждый запуск и разными форматами.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Форматтер с ANSI-цветами ТОЛЬКО для консоли. Сами записи не меняет."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        # Применяем цвет ко всей строке, не меняя атрибуты record
        color = self.COLORS.get(record.levelno, "")
        formatted = super().format(record)
        if color:
            return f"{color}{formatted}{self.RESET}"
        return formatted


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Настройка корневого логгера StepWise Alchemy.

    Args:
        log_dir: директория для лог-файлов
        log_level: уровень корневого логгера
        console_level: уровень для вывода в консоль
        file_level: уровень для вывода в файл
        max_bytes: максимальный размер одного лог-файла
        backup_count: количество ротируемых файлов

    Returns:
        Корневой логгер проекта ("stepwise")
    """

    # Создаём директорию для логов
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Имя файла с меткой времени запуска
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_path / f"stepwise_{timestamp}.log"

    # Корневой логгер проекта
    logger = logging.getLogger("stepwise")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Очищаем существующие хендлеры (на случай повторного вызова)
    logger.handlers.clear()

    # --- Консольный хендлер ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_format = ColoredFormatter(
        "%(levelname)-8s | %(name)s | %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # --- Файловый хендлер с ротацией ---
    file_handler = logging.handlers.RotatingFileHandler(
        log_filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Отключаем propagation, чтобы не дублировалось в корневой логгер Python
    logger.propagate = False

    logger.info("Логирование настроено: level=%s, dir=%s", log_level, log_dir)
    logger.info("Лог-файл: %s", log_filename)
    logger.debug("Консоль: %s, Файл: %s, Ротация: %d x %dMB",
                 console_level, file_level, backup_count, max_bytes // (1024*1024))

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер с неймспейсом stepwise.{name}.
    Пример: logger = get_logger(__name__.replace('stepwise_alchemy.', ''))
    """
    return logging.getLogger(f"stepwise.{name}")