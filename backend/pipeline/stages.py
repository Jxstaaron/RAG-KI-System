from __future__ import annotations
"""Einzelne Pipeline-Stufen und Orchestrierung der kompletten Verarbeitung."""

import argparse
from pathlib import Path
from typing import Callable

from backend.pipeline.chunking import chunk_blocks, chunks_to_markdown
from backend.pipeline.config import (
    CHUNKS,
    CLEANED,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDINGS,
    EXTRACTED,
    STRUCTURED,
    path_for,
)
from backend.pipeline.embeddings import embed_chunks
from backend.pipeline.extraction import extract_pdf
from backend.pipeline.io import read_json, read_text, write_json, write_text
from backend.pipeline.text_processing import clean_text, structure_text


def run_extract(pdf: str | Path, output: str | Path | None = None) -> str:
    """Extrahiert Text und Layoutinformationen aus einer PDF-Datei."""

    output = output or path_for(EXTRACTED, pdf, ".md")
    print(f"Extracting PDF: {pdf}")
    text = extract_pdf(pdf)
    write_text(output, text)
    print(f"Saved extracted text to: {output}")
    return text


def run_clean(source: str | Path, output: str | Path | None = None) -> str:
    """Bereinigt den extrahierten Markdown-/OCR-Text."""

    output = output or path_for(CLEANED, source, ".txt")
    text = clean_text(read_text(source))
    write_text(output, text)
    print(f"Saved cleaned text to: {output}")
    return text


def run_structure(source: str | Path, output: str | Path | None = None) -> list[dict]:
    """Wandelt den bereinigten Text in strukturierte Textblöcke um."""

    output = output or path_for(STRUCTURED, source, ".json")
    blocks = structure_text(read_text(source))
    write_json(output, blocks)
    print(f"Saved {len(blocks)} structured blocks to: {output}")
    return blocks


def run_chunk(
    source: str | Path,
    output: str | Path | None = None,
    markdown: str | Path | None = None,
) -> list[dict]:
    """Erstellt aus strukturierten Blöcken größere RAG-Chunks."""

    output = output or path_for(CHUNKS, source, ".json")
    markdown = markdown or path_for(CHUNKS, source, ".md")
    chunks = chunk_blocks(read_json(source))
    write_json(output, chunks)
    write_text(markdown, chunks_to_markdown(chunks))
    print(f"Saved {len(chunks)} chunks to: {output}")
    print(f"Saved chunk preview to: {markdown}")
    return chunks


ProgressCallback = Callable[[str, str, int], None]


def run_all(
    pdf: str | Path,
    args: argparse.Namespace,
    progress_callback: ProgressCallback | None = None,
) -> None:
    """Führt die komplette Pipeline von PDF bis Embeddings aus."""

    extracted = getattr(args, "extracted_output", None) or path_for(EXTRACTED, pdf, ".md")
    cleaned = getattr(args, "cleaned_output", None) or path_for(CLEANED, pdf, ".txt")
    structured = getattr(args, "structured_output", None) or path_for(STRUCTURED, cleaned, ".json")
    chunks = getattr(args, "chunks_output", None) or path_for(CHUNKS, structured, ".json")
    chunks_markdown = getattr(args, "chunks_markdown_output", None) or path_for(CHUNKS, structured, ".md")
    embeddings = getattr(args, "embeddings_output", None) or path_for(EMBEDDINGS, chunks, ".npy")
    embedding_model = getattr(args, "embedding_model", DEFAULT_EMBEDDING_MODEL)

    def update(stage: str, label: str, progress: int) -> None:
        # Der Callback ist optional, weil die CLI keinen Live-Fortschritt
        # braucht, das Web-Frontend aber schon.
        if progress_callback:
            progress_callback(stage, label, progress)

    update("extracting", "Text extrahieren", 15)
    run_extract(pdf, extracted)
    update("cleaning", "Text bereinigen", 55)
    run_clean(extracted, cleaned)
    update("structuring", "Struktur erkennen", 65)
    run_structure(cleaned, structured)
    update("chunking", "Chunks erstellen", 75)
    run_chunk(structured, chunks, chunks_markdown)
    update("embedding", "Embeddings berechnen", 90)
    embed_chunks(chunks, embeddings, embedding_model)
    update("done", "Fertig", 100)
