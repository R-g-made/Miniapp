from typing import Generic, TypeVar, Any
from abc import ABC, abstractmethod

T = TypeVar("T")

class BaseBuilder(ABC, Generic[T]):
    """Абстрактный базовый класс для всех билдеров ответов"""
    
    def __init__(self):
        self._reset()

    @abstractmethod
    def _reset(self) -> None:
        """Сброс состояния билдера (инициализация полей)"""
        pass

    @abstractmethod
    def build(self) -> T:
        """Сборка финального объекта/схемы"""
        pass
