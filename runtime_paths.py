from pathlib import Path

DATA_UPLOAD_DIR = Path("data/uploads")
DATA_OUTPUT_DIR = Path("data/outputs")
ANNOTATED_DATASET_DIR = Path("storage/datasets")

RUNTIME_DIRECTORIES = (
    DATA_UPLOAD_DIR,
    DATA_OUTPUT_DIR,
    ANNOTATED_DATASET_DIR,
)


def ensure_runtime_directories() -> None:
    """Create ignored runtime directories required by the API at startup."""
    for directory in RUNTIME_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
