from abc import ABC, abstractmethod
from typing import Any

from polish_dataset_translator.models import RecordPlan


class BfclAdapter(ABC):
    @abstractmethod
    def plan(self, record: dict[str, Any], source_name: str) -> RecordPlan:
        """Classify a BFCL record and return safe natural-language targets."""

    @abstractmethod
    def apply(self, record: dict[str, Any], translations: dict[tuple[str | int, ...], str]) -> dict[str, Any]:
        """Apply translated values without changing record shape."""

    @abstractmethod
    def category(self, record: dict[str, Any], source_name: str) -> str:
        """Return the most specific known BFCL category."""