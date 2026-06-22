from pathlib import Path

OUTPUT_DIR = Path("data/outputs")


def ensure_runtime_directories() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
