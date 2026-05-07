"""
Реестр источников StepWise Alchemy.
Автоматически обнаруживает модули в пакете sources/ и регистрирует их.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Optional

from core.source_base import BaseSource
from utils.logging_setup import get_logger

logger = get_logger("registry")


class SourceRegistry:
    """Хранит все зарегистрированные источники."""

    def __init__(self):
        self._sources: Dict[str, BaseSource] = {}

    def register(self, source_class: type) -> None:
        """
        Регистрирует класс источника.
        Вызывается из модуля источника через декоратор @register_source.
        """
        if not issubclass(source_class, BaseSource):
            logger.error(
                "Класс %s не является наследником BaseSource, пропущен",
                source_class.__name__,
            )
            return

        # Создаём экземпляр
        instance = source_class()
        name = instance.name

        if name in self._sources:
            logger.warning(
                "Источник '%s' уже зарегистрирован, перезаписан (класс: %s)",
                name,
                source_class.__name__,
            )

        self._sources[name] = instance
        logger.info(
            "Зарегистрирован источник '%s': tier=%d, type=%s, класс=%s",
            name,
            instance.quality_tier,
            instance.content_type,
            source_class.__name__,
        )

    def get(self, name: str) -> Optional[BaseSource]:
        """Получить источник по имени."""
        return self._sources.get(name)

    def list_all(self) -> Dict[str, BaseSource]:
        """Вернуть все зарегистрированные источники."""
        return dict(self._sources)

    def __len__(self) -> int:
        return len(self._sources)

    def __contains__(self, name: str) -> bool:
        return name in self._sources


# Глобальный экземпляр реестра
_registry = SourceRegistry()


def register_source(cls: type) -> type:
    """Декоратор для регистрации источника."""
    _registry.register(cls)
    return cls


def load_registry() -> SourceRegistry:
    """
    Автоматически обнаруживает и загружает все модули из пакета sources/.
    Каждый модуль при импорте сам регистрирует свой класс через @register_source.
    """
    try:
        import sources as sources_pkg
    except ImportError:
        logger.error("Пакет 'sources' не найден. Создайте директорию sources/ с __init__.py")
        return _registry

    pkg_path = Path(sources_pkg.__file__).parent

    logger.info("Поиск источников в %s", pkg_path)

    found_modules = 0
    for _, module_name, is_pkg in pkgutil.iter_modules([str(pkg_path)]):
        if is_pkg:
            continue  # пропускаем подпакеты

        try:
            importlib.import_module(f"sources.{module_name}")
            found_modules += 1
            logger.debug("Загружен модуль: sources.%s", module_name)
        except Exception as e:
            logger.error(
                "Ошибка при загрузке модуля sources.%s: %s",
                module_name,
                e,
                exc_info=True,
            )

    logger.info("Загружено модулей: %d, зарегистрировано источников: %d",
                found_modules, len(_registry))

    return _registry


def resolve_sources(
    registry: SourceRegistry,
    cli_source: Optional[str] = None,
    config_sources: Optional[dict] = None,
) -> list:
    """
    Определяет итоговый список имён источников для обработки.

    Args:
        registry: реестр источников
        cli_source: имя источника, переданное через --source (может быть None)
        config_sources: словарь из config.yaml с настройками источников

    Returns:
        Список имён источников (строк)
    """
    if cli_source:
        # Явно указан один источник через CLI
        if cli_source not in registry:
            logger.error(
                "Источник '%s' не найден в реестре. Доступные: %s",
                cli_source,
                list(registry.list_all().keys()),
            )
            return []
        logger.info("Выбран источник (из CLI): %s", cli_source)
        return [cli_source]

    # Выбираем из конфига
    if config_sources:
        active = []
        for name, cfg in config_sources.items():
            if not cfg.get("enabled", True):
                logger.debug("Источник '%s' отключён в конфиге", name)
                continue
            if name not in registry:
                logger.warning(
                    "Источник '%s' указан в конфиге, но не найден в реестре. Пропущен.",
                    name,
                )
                continue
            active.append(name)
        logger.info("Выбраны источники из конфига: %s", active)
        return active

    # Если ни CLI, ни конфиг — берём все зарегистрированные
    all_sources = list(registry.list_all().keys())
    logger.info("Выбраны все зарегистрированные источники: %s", all_sources)
    return all_sources