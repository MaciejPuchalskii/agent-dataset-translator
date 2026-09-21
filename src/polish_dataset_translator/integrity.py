import json
from typing import Any

TECHNICAL_KEYS = {"id", "ground_truth", "possible_answer", "initial_config", "involved_classes", "missed_function", "scenario", "function_call", "tool_call_id", "tool_calls"}
SCHEMA_KEYS = {"name", "type", "properties", "required", "enum", "items", "additionalProperties"}


def _is_code_or_url(value: str) -> bool:
    lowered = value.lower()
    return "http://" in lowered or "https://" in lowered or any(token in lowered for token in ("def ", "select ", "insert ", "update ", "delete ", "class "))


def technical_snapshot(value: Any, path: tuple[str | int, ...] = ()) -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (key,)
            if key in TECHNICAL_KEYS:
                result[".".join(map(str, child_path))] = json.dumps(child, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            elif key in {"properties", "items", "additionalProperties"}:
                result.update(technical_snapshot(child, child_path))
            elif key in SCHEMA_KEYS:
                result[".".join(map(str, child_path))] = json.dumps(child, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            else:
                result.update(technical_snapshot(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(technical_snapshot(child, path + (index,)))
    elif isinstance(value, str) and _is_code_or_url(value):
        result[".".join(map(str, path))] = value
    return result


def validate_integrity(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if before.get("id") != after.get("id"):
        errors.append("record id changed")
    before_snapshot = technical_snapshot(before)
    after_snapshot = technical_snapshot(after)
    for path, expected in before_snapshot.items():
        if after_snapshot.get(path) != expected:
            errors.append(f"technical field changed: {path}")
    if set(before) != set(after):
        errors.append("top-level keys changed")
    return errors