from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend" / "data"
PDFS = DATA / "pdfs"
EXTRACTED = DATA / "extracted_text"
CLEANED = DATA / "cleaned_text"
STRUCTURED = DATA / "structured_blocks"
CHUNKS = DATA / "chunks"
EMBEDDINGS = DATA / "embeddings"

DEFAULT_PDF = PDFS / "file.pdf"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def ensure_output_dirs() -> None:
    for path in (PDFS, EXTRACTED, CLEANED, STRUCTURED, CHUNKS, EMBEDDINGS):
        path.mkdir(parents=True, exist_ok=True)


def path_for(folder: Path, source: str | Path, suffix: str) -> Path:
    return folder / f"{Path(source).stem}{suffix}"
