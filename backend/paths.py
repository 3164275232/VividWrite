from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CHARTS_DIR = BASE_DIR / "generated_charts"
UPLOADS_DIR = BASE_DIR / "uploaded_images"
USER_DATA_DIR = BASE_DIR / "user_data"


def ensure_runtime_directories() -> None:
    for directory in (CHARTS_DIR, UPLOADS_DIR, USER_DATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)
