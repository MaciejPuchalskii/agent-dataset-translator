import csv
import json
from pathlib import Path
from typing import Protocol

from polish_dataset_translator.adapters.bfcl import BfclJsonlAdapter
from polish_dataset_translator.integrity import validate_integrity
from polish_dataset_translator.io import (
    append_jsonl,
    iter_jsonl_files,
    load_checkpoint,
    read_jsonl,
    record_fingerprint,
    save_checkpoint,
)
from polish_dataset_translator.models import RecordReport, RunReport


class Translator(Protocol):
    def translate(self, text: str) -> str: ...

    def translate_many(self, texts: list[str]) -> list[str]: ...


class TranslationPipeline:
    def __init__(self, translator: Translator, adapter: BfclJsonlAdapter | None = None, batch_size: int = 20) -> None:
        self.translator = translator
        self.adapter = adapter or BfclJsonlAdapter()
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")
        self.batch_size = batch_size

    def run(self, input_path: Path, output_path: Path, report_path: Path) -> RunReport:
        files = iter_jsonl_files(input_path)
        report = RunReport(input_files=len(files))
        checkpoint_path = output_path.with_suffix(output_path.suffix + ".checkpoint.json")
        checkpoint = load_checkpoint(checkpoint_path)
        pending: list[dict[str, object]] = []
        pending_target_count = 0

        def flush_pending() -> None:
            nonlocal pending, pending_target_count
            if not pending:
                return
            target_refs = [
                (entry, target)
                for entry in pending
                for target in entry["plan"].targets  # type: ignore[union-attr]
            ]
            try:
                texts = [target.text for _, target in target_refs]
                if hasattr(self.translator, "translate_many"):
                    values = self.translator.translate_many(texts)
                else:
                    values = [self.translator.translate(text) for text in texts]
                if len(values) != len(target_refs):
                    raise ValueError(f"translator returned {len(values)} values for {len(target_refs)} targets")
                for (entry, target), value in zip(target_refs, values):
                    entry["translated"][target.path] = value  # type: ignore[index]
                    if not self.adapter.placeholders_match(target.text, value):
                        entry["plan"].review_reasons.append(f"placeholder mismatch at {'.'.join(map(str, target.path))}")  # type: ignore[union-attr]
            except Exception as error:  # noqa: BLE001 - isolate failed batches in reports
                for entry in pending:
                    record_id = entry["record_id"]  # type: ignore[assignment]
                    report.failed_records += 1
                    report.records.append(RecordReport(str(record_id), "unknown", "failed", error=str(error)))
                    print(f"[record {record_id}] failed batch: {error}", flush=True)
                pending = []
                pending_target_count = 0
                return

            for entry in pending:
                record = entry["record"]  # type: ignore[assignment]
                plan = entry["plan"]  # type: ignore[assignment]
                record_id = entry["record_id"]  # type: ignore[assignment]
                fingerprint = entry["fingerprint"]  # type: ignore[assignment]
                try:
                    result = self.adapter.apply(record, entry["translated"])  # type: ignore[arg-type]
                    errors = validate_integrity(record, result)
                    if errors:
                        raise ValueError("; ".join(errors))
                    append_jsonl(output_path, result)
                    checkpoint[str(record_id)] = str(fingerprint)
                    save_checkpoint(checkpoint_path, checkpoint)
                    print(f"[record {record_id}] saved to {output_path}", flush=True)
                    status = "review" if plan.review_reasons else "translated"
                    if status == "review":
                        report.review_records += 1
                    else:
                        report.translated_records += 1
                    report.records.append(RecordReport(str(record_id), plan.category, status, len(entry["translated"]), plan.review_reasons))
                except Exception as error:  # noqa: BLE001 - isolate failed records in batch reports
                    report.failed_records += 1
                    report.records.append(RecordReport(str(record_id), "unknown", "failed", error=str(error)))
                    print(f"[record {record_id}] failed: {error}", flush=True)
            pending = []
            pending_target_count = 0

        for source in files:
            for _, record in read_jsonl(source):
                report.input_records += 1
                record_id = str(record.get("id", f"{source.name}:{report.input_records}"))
                fingerprint = record_fingerprint(record)
                if checkpoint.get(record_id) == fingerprint:
                    report.skipped_records += 1
                    report.records.append(RecordReport(record_id, "unknown", "skipped"))
                    print(f"[record {record_id}] skipped: already checkpointed", flush=True)
                    continue
                try:
                    plan = self.adapter.plan(record, source.name)
                    print(f"[record {record_id}] category={plan.category}, targets={len(plan.targets)}", flush=True)
                    if pending and pending_target_count + len(plan.targets) > self.batch_size:
                        flush_pending()
                    if not plan.targets:
                        pending.append({"record": record, "plan": plan, "record_id": record_id, "fingerprint": fingerprint, "translated": {}})
                        flush_pending()
                    else:
                        pending.append({"record": record, "plan": plan, "record_id": record_id, "fingerprint": fingerprint, "translated": {}})
                        pending_target_count += len(plan.targets)
                        if pending_target_count >= self.batch_size:
                            flush_pending()
                except Exception as error:  # noqa: BLE001 - isolate failed records in batch reports
                    report.failed_records += 1
                    report.records.append(RecordReport(record_id, "unknown", "failed", error=str(error)))
                    print(f"[record {record_id}] failed: {error}", flush=True)
        flush_pending()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, default=lambda item: item.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        with report_path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "category", "status", "translated_fields", "review_reasons", "error"])
            writer.writeheader()
            for item in report.records:
                writer.writerow({"record_id": item.record_id, "category": item.category, "status": item.status, "translated_fields": item.translated_fields, "review_reasons": " | ".join(item.review_reasons), "error": item.error or ""})
        review_path = report_path.with_suffix(".review.jsonl")
        with review_path.open("w", encoding="utf-8") as handle:
            for item in report.records:
                if item.status == "review" or item.status == "failed":
                    handle.write(json.dumps(item, default=lambda value: value.__dict__, ensure_ascii=False) + "\n")
        print(f"[report] saved JSON: {report_path}", flush=True)
        print(f"[report] saved CSV: {report_path.with_suffix('.csv')}", flush=True)
        print(f"[report] saved review list: {review_path}", flush=True)
        return report