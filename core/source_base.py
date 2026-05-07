"""
Базовый класс для всех источников данных StepWise Alchemy.
"""

from abc import ABC, abstractmethod
from typing import Iterator


class BaseSource(ABC):
    """Минимальный интерфейс источника данных."""

    name: str
    quality_tier: int
    content_type: str  # "dialogue" или "text"

    @abstractmethod
    def extract(self) -> Iterator[dict]:
        """Генератор сырых записей из источника."""
        ...