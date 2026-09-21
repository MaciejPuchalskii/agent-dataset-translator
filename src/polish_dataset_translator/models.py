from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranslationTarget:
    path: tuple[str | int, ...]
    text: str
    reason: str


@dataclass
class RecordPlan:
    record_id: str
    category: str
    targets: list[TranslationTarget] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class RecordReport:
    record_id: str
    category: str
    status: str
    translated_fields: int = 0
    review_reasons: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunReport:
    input_files: int = 0
    input_records: int = 0
    translated_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0
    review_records: int = 0
    records: list[RecordReport] = field(default_factory=list)