from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "backend" / "data"
PDF_INPUT_DIR = DATA_DIR / "pdfs"
EXTRACTED_TEXT_DIR = DATA_DIR / "extracted_text"
CLEANED_TEXT_DIR = DATA_DIR / "cleaned_text"
STRUCTURED_BLOCKS_DIR = DATA_DIR / "structured_blocks"
CHUNKS_DIR = DATA_DIR / "chunks"


def ensure_data_dirs():
    for directory in (
        PDF_INPUT_DIR,
        EXTRACTED_TEXT_DIR,
        CLEANED_TEXT_DIR,
        STRUCTURED_BLOCKS_DIR,
        CHUNKS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def extracted_text_path_for(pdf_path: str | Path) -> Path:
    return EXTRACTED_TEXT_DIR / f"{Path(pdf_path).stem}.md"


def cleaned_text_path_for(pdf_path: str | Path) -> Path:
    return CLEANED_TEXT_DIR / f"{Path(pdf_path).stem}.txt"


def structured_blocks_path_for(input_path: str | Path) -> Path:
    return STRUCTURED_BLOCKS_DIR / f"{Path(input_path).stem}.json"


def chunks_path_for(input_path: str | Path) -> Path:
    return CHUNKS_DIR / f"{Path(input_path).stem}.json"


def chunks_markdown_path_for(input_path: str | Path) -> Path:
    return CHUNKS_DIR / f"{Path(input_path).stem}.md"
