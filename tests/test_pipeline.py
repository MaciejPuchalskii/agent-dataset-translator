import json

from polish_dataset_translator.pipeline import TranslationPipeline


class FakeTranslator:
    def __init__(self) -> None:
        self.batch_calls = 0

    def translate(self, text: str) -> str:
        return "PL: " + text.replace("{city}", "{city}")

    def translate_many(self, texts: list[str]) -> list[str]:
        self.batch_calls += 1
        return [self.translate(text) for text in texts]


def test_pipeline_writes_checkpoint_and_review_outputs(tmp_path) -> None:
    source = tmp_path / "simple_python.jsonl"
    records = [
        {"id": "simple_python_1", "question": [[{"role": "user", "content": "Hello {city}"}]], "function": [], "ground_truth": []},
        {"id": "simple_python_2", "question": [[{"role": "user", "content": "Goodbye {city}"}]], "function": [], "ground_truth": []},
    ]
    source.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    output = tmp_path / "translated.jsonl"
    report_path = tmp_path / "reports" / "run.json"
    translator = FakeTranslator()
    pipeline = TranslationPipeline(translator, batch_size=2)
    first = pipeline.run(source, output, report_path)
    second = pipeline.run(source, output, report_path)
    assert first.translated_records == 2
    assert translator.batch_calls == 1
    assert second.skipped_records == 2
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2
    assert report_path.with_suffix(".csv").exists()
    assert report_path.with_suffix(".review.jsonl").exists()


def test_directory_output_preserves_structure_and_adds_polish_prefix(tmp_path) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    source = input_dir / "BFCL_v3_chatable.json"
    source.write_text(json.dumps({"id": "chat_1", "question": [[{"role": "user", "content": "Hello"}]], "function": [], "ground_truth": []}) + "\n", encoding="utf-8")
    output_dir = tmp_path / "translated"
    pipeline = TranslationPipeline(FakeTranslator(), batch_size=20)

    pipeline.run(input_dir, output_dir, tmp_path / "reports" / "run.json")

    assert (output_dir / "BFCL_PL_v3_chatable.json").exists()
    assert not (output_dir / "BFCL_v3_chatable.json").exists()