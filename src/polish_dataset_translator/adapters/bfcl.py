import copy
import re
from typing import Any

from polish_dataset_translator.adapters.base import BfclAdapter
from polish_dataset_translator.models import RecordPlan, TranslationTarget

_PLACEHOLDER = re.compile(r"(\{\{?[^{}]+\}?\}|<[^>]+>|\$\{[^}]+\})")
_ROLE_TRANSLATABLE = {"user", "system"}


def _looks_natural(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and not stripped.startswith(("http://", "https://", "/", "./"))


class BfclJsonlAdapter(BfclAdapter):
    def category(self, record: dict[str, Any], source_name: str) -> str:
        identifier = str(record.get("id", ""))
        categories = ("format_sensitivity", "web_search", "memory", "multi_turn_long_context", "multi_turn_miss_func", "multi_turn_miss_param", "multi_turn_base", "live_parallel_multiple", "live_parallel", "live_multiple", "live_simple", "live_irrelevance", "live_relevance", "parallel_multiple", "parallel", "multiple", "simple_python", "simple_java", "simple_javascript", "irrelevance")
        return next((category for category in categories if category in identifier or category in source_name), "unknown")

    def plan(self, record: dict[str, Any], source_name: str) -> RecordPlan:
        category = self.category(record, source_name)
        plan = RecordPlan(str(record.get("id", "")), category)
        self._collect_messages(record, plan)
        self._collect_function_descriptions(record, plan)
        if category == "unknown":
            plan.review_reasons.append("unknown BFCL category")
        if category in {"web_search", "memory"}:
            plan.review_reasons.append(f"sensitive agentic category: {category}")
        return plan

    def _collect_messages(self, record: dict[str, Any], plan: RecordPlan) -> None:
        question = record.get("question")
        if not isinstance(question, list):
            return
        for turn_index, turn in enumerate(question):
            if not isinstance(turn, list):
                continue
            for message_index, message in enumerate(turn):
                if not isinstance(message, dict) or message.get("role") not in _ROLE_TRANSLATABLE:
                    continue
                content = message.get("content")
                if isinstance(content, str) and _looks_natural(content):
                    plan.targets.append(TranslationTarget(("question", turn_index, message_index, "content"), content, "message content"))

    def _collect_function_descriptions(self, record: dict[str, Any], plan: RecordPlan) -> None:
        functions = record.get("function")
        if not isinstance(functions, list):
            return
        for function_index, function in enumerate(functions):
            if not isinstance(function, dict):
                continue
            description = function.get("description")
            if isinstance(description, str) and _looks_natural(description):
                plan.targets.append(TranslationTarget(("function", function_index, "description"), description, "function description"))
            self._collect_parameter_descriptions(function.get("parameters"), ("function", function_index, "parameters"), plan)

    def _collect_parameter_descriptions(self, value: Any, path: tuple[str | int, ...], plan: RecordPlan) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = path + (key,)
                if key == "description" and isinstance(child, str) and _looks_natural(child):
                    plan.targets.append(TranslationTarget(child_path, child, "parameter description"))
                elif key not in {"name", "type", "enum", "required", "default"}:
                    self._collect_parameter_descriptions(child, child_path, plan)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._collect_parameter_descriptions(child, path + (index,), plan)

    def apply(self, record: dict[str, Any], translations: dict[tuple[str | int, ...], str]) -> dict[str, Any]:
        result = copy.deepcopy(record)
        for path, translated in translations.items():
            cursor: Any = result
            for part in path[:-1]:
                cursor = cursor[part]
            cursor[path[-1]] = translated
        return result

    @staticmethod
    def placeholders_match(source: str, translated: str) -> bool:
        return _PLACEHOLDER.findall(source) == _PLACEHOLDER.findall(translated)