from polish_dataset_translator.adapters.bfcl import BfclJsonlAdapter
from polish_dataset_translator.integrity import validate_integrity


def test_single_turn_translates_only_question_and_descriptions() -> None:
    record = {
        "id": "simple_python_1",
        "question": [[{"role": "user", "content": "What is the weather in {city}?"}]],
        "function": [{"name": "get_weather", "description": "Get current weather.", "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "Name of the city."}}, "required": ["city"]}}],
        "ground_truth": [["get_weather(city='Warsaw')"]],
    }
    adapter = BfclJsonlAdapter()
    plan = adapter.plan(record, "BFCL_v4_simple_python.json")
    result = adapter.apply(record, {target.path: "PL:" + target.text for target in plan.targets})
    assert result["question"][0][0]["content"].startswith("PL:")
    assert result["function"][0]["name"] == "get_weather"
    assert result["function"][0]["parameters"]["properties"]["city"]["type"] == "string"
    assert result["ground_truth"] == record["ground_truth"]
    assert validate_integrity(record, result) == []


def test_multi_turn_preserves_assistant_and_tool_messages() -> None:
    record = {
        "id": "multi_turn_base_1",
        "question": [[{"role": "user", "content": "Find my booking."}], [{"role": "assistant", "content": "get_booking(id='x')"}], [{"role": "user", "content": "Thanks."}]],
        "function": [],
        "ground_truth": [["get_booking"], ["confirm"]],
        "initial_config": {"booking_id": "x"},
    }
    adapter = BfclJsonlAdapter()
    plan = adapter.plan(record, "multi_turn_base.json")
    assert len(plan.targets) == 2
    result = adapter.apply(record, {target.path: "PL:" + target.text for target in plan.targets})
    assert result["question"][1][0]["content"] == "get_booking(id='x')"
    assert result["initial_config"] == record["initial_config"]
    assert validate_integrity(record, result) == []