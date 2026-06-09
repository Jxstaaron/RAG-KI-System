from __future__ import annotations
"""FastAPI-Backend für die PDF-RAG-Webapp.

Diese Datei verbindet die React-Oberfläche mit der eigentlichen Pipeline:
PDF hochladen, Pipeline ausführen, Antwort generieren und Ergebnis als PDF
herunterladen.
"""

import argparse
import shutil
from threading import Lock
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.pdf_export import export_answer_pdf
from backend.pipeline.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    DEFAULT_PDF,
    CHUNKS,
    EMBEDDINGS,
    GENERATED,
    PDFS,
    ensure_output_dirs,
    path_for,
)
from backend.pipeline.generation import generate_answer, generate_from_chunks
from backend.pipeline.io import read_json
from backend.pipeline.stages import run_all

app = FastAPI(title="PDF Learning Assistant")

# CORS erlaubt dem Next.js-Frontend, das lokal oder über das Netzwerk läuft,
# Requests an dieses Backend zu senden.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=(
        r"http://("
        r"localhost|"
        r"127\.0\.0\.1|"
        r"10\.\d+\.\d+\.\d+|"
        r"192\.168\.\d+\.\d+|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+"
        r"):\d+"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    """Datenmodell für eine Generierungsanfrage aus dem Frontend."""

    mode: str
    query: str | None = None
    top_k: int = 5
    min_score: float = 0.5
    llm_model: str = DEFAULT_OLLAMA_MODEL


LAST_ANSWER_PATH = GENERATED / "last_answer.txt"
LAST_PDF_PATH = GENERATED / "output.pdf"
PROGRESS_LOCK = Lock()
# Der Fortschritt wird im Speicher gehalten, damit das Frontend während des
# langen Upload-/OCR-Vorgangs regelmäßig /progress abfragen kann.
PIPELINE_PROGRESS = {
    "status": "idle",
    "stage": "idle",
    "label": "Bereit",
    "progress": 0,
}


def set_pipeline_progress(status: str, stage: str, label: str, progress: int) -> None:
    """Aktualisiert den globalen Pipeline-Fortschritt thread-sicher."""

    with PROGRESS_LOCK:
        PIPELINE_PROGRESS.update(
            {
                "status": status,
                "stage": stage,
                "label": label,
                "progress": progress,
            }
        )


def default_query(mode: str) -> str:
    """Standard-Aufgabenstellung für die festen Modi ohne Custom-Frage."""

    prompts = {
        "cheatsheet": "Erstelle einen Spickzettel zu den wichtigsten Inhalten.",
        "summary": "Fasse die wichtigsten Inhalte zusammen.",
        "quiz": "Erstelle ein Quiz zu den wichtigsten Inhalten.",
        "flashcards": "Erstelle Karteikarten zu den wichtigsten Inhalten.",
        "explanation": "Erkläre die wichtigsten Inhalte einfach und verständlich.",
    }
    return prompts.get(mode, prompts["explanation"])


def has_custom_query(query: str | None) -> bool:
    """Prueft, ob der User wirklich eine eigene Frage eingegeben hat."""

    return bool(query and query.strip())


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/progress")
def progress() -> dict[str, str | int]:
    with PROGRESS_LOCK:
        return dict(PIPELINE_PROGRESS)


@app.post("/upload")
def upload_pdf(file: UploadFile = File(...)) -> dict[str, str]:
    """Speichert die hochgeladene PDF und startet danach die komplette Pipeline."""

    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    ensure_output_dirs()
    set_pipeline_progress("running", "uploading", "PDF hochladen", 5)
    pdf_path = PDFS / "file.pdf"
    with pdf_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)
    set_pipeline_progress("running", "saved", "PDF gespeichert", 10)

    # Die Pipeline-Funktionen werden auch von der CLI genutzt und erwarten ein
    # argparse-Objekt. Hier erzeugen wir dasselbe Objekt manuell für die API.
    args = argparse.Namespace(
        extracted_output=None,
        cleaned_output=None,
        structured_output=None,
        chunks_output=None,
        chunks_markdown_output=None,
        embeddings_output=None,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
    )
    try:
        run_all(
            pdf_path,
            args,
            progress_callback=lambda stage, label, progress: set_pipeline_progress(
                "running" if stage != "done" else "done",
                stage,
                label,
                progress,
            ),
        )
    except ModuleNotFoundError as exc:
        if exc.name == "marker":
            set_pipeline_progress("error", "error", "Fehler: marker-pdf fehlt", 0)
            raise HTTPException(
                status_code=500,
                detail=(
                    "Missing dependency: marker-pdf. Install project requirements in the same "
                    "environment that runs FastAPI with: pip install -r requirements.txt"
                ),
            ) from exc
        raise
    except Exception:
        set_pipeline_progress("error", "error", "Pipeline fehlgeschlagen", 0)
        raise
    return {"status": "processed", "filename": file.filename or pdf_path.name}


@app.post("/generate")
def generate(request: GenerateRequest) -> dict[str, str]:
    """Generiert eine Antwort aus den gespeicherten Chunks und Embeddings."""

    ensure_output_dirs()
    embeddings = path_for(EMBEDDINGS, DEFAULT_PDF, ".npy")
    chunks_path = path_for(CHUNKS, DEFAULT_PDF, ".json")
    if not Path(embeddings).exists():
        raise HTTPException(status_code=400, detail="Upload and process a PDF first.")

    if request.mode == "custom" and not has_custom_query(request.query):
        raise HTTPException(status_code=400, detail="Custom mode needs a question.")

    if has_custom_query(request.query):
        # Custom-Fragen nutzen Retrieval: Nur die passendsten Chunks werden in
        # den Prompt gegeben.
        answer = generate_answer(
            request.query or default_query(request.mode),
            embeddings,
            mode=request.mode,
            top_k=request.top_k,
            min_score=request.min_score,
            provider="ollama",
            llm_model=request.llm_model,
            ollama_url=DEFAULT_OLLAMA_URL,
        )
    else:
        # Feste Modi wie Spickzettel/Zusammenfassung verwenden alle Chunks,
        # damit ein Gesamtüberblick über die PDF entsteht.
        if not chunks_path.exists():
            raise HTTPException(status_code=400, detail="Upload and process a PDF first.")
        answer = generate_from_chunks(
            default_query(request.mode),
            read_json(chunks_path),
            mode=request.mode,
            provider="ollama",
            llm_model=request.llm_model,
            ollama_url=DEFAULT_OLLAMA_URL,
        )

    LAST_ANSWER_PATH.write_text(answer, encoding="utf-8")
    export_answer_pdf(answer, LAST_PDF_PATH.name)
    return {"answer": answer}


@app.get("/download")
def download_pdf() -> FileResponse:
    """Gibt die zuletzt generierte Antwort als PDF-Datei zurück."""

    if not LAST_PDF_PATH.exists():
        raise HTTPException(status_code=404, detail="No generated PDF is available yet.")
    return FileResponse(
        LAST_PDF_PATH,
        media_type="application/pdf",
        filename="learning-material.pdf",
    )
