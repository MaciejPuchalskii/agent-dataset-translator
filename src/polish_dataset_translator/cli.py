from pathlib import Path

import typer
from huggingface_hub import HfApi, hf_hub_download

from polish_dataset_translator.config import Settings
from polish_dataset_translator.pipeline import TranslationPipeline
from polish_dataset_translator.providers.azure_foundry import AzureFoundryTranslator

app = typer.Typer(no_args_is_help=True)


@app.command()
def download(
    output: Path = typer.Option(..., help="Directory for downloaded BFCL JSON/JSONL files."),  # noqa: B008
    repo_id: str = typer.Option("gorilla-llm/Berkeley-Function-Calling-Leaderboard", help="Hugging Face dataset repository."),
) -> None:
    """Download BFCL line-delimited JSON files without using datasets.load_dataset."""
    output.mkdir(parents=True, exist_ok=True)
    files = [name for name in HfApi().list_repo_files(repo_id, repo_type="dataset") if name.endswith((".json", ".jsonl"))]
    if not files:
        raise typer.BadParameter("The repository exposes no JSON or JSONL files")
    for name in files:
        local_path = hf_hub_download(repo_id, name, repo_type="dataset", local_dir=str(output))
        typer.echo(local_path)


@app.command()
def translate(
    input: Path = typer.Option(..., exists=True, readable=True, help="BFCL JSONL file or directory."),  # noqa: B008
    output: Path = typer.Option(..., help="Output JSONL file."),  # noqa: B008
    report: Path = typer.Option(..., help="Quality report JSON."),  # noqa: B008
    batch_size: int = typer.Option(20, min=1, max=100, help="Number of texts sent in one model request."),
) -> None:
    """Translate BFCL natural-language fields using Azure Foundry."""
    typer.echo(f"Starting translation: {input} -> {output}")
    run_report = TranslationPipeline(AzureFoundryTranslator(Settings.from_env()), batch_size=batch_size).run(input, output, report)
    typer.echo(f"translated={run_report.translated_records} review={run_report.review_records} failed={run_report.failed_records}")


if __name__ == "__main__":
    app()