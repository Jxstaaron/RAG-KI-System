from __future__ import annotations
"""Kommandozeilen-Interface zum Testen einzelner Pipeline-Schritte."""

import argparse
import os

from backend.pipeline.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_OLLAMA_URL,
    DEFAULT_PDF,
    EMBEDDINGS,
    ensure_output_dirs,
    path_for,
)
from backend.pipeline.embeddings import embed_chunks
from backend.pipeline.generation import generate_answer
from backend.pipeline.retrieval import print_results, retrieve_chunks
from backend.pipeline.stages import run_all, run_chunk, run_clean, run_extract, run_structure


def parse_args() -> argparse.Namespace:
    """Definiert alle CLI-Befehle wie extract, chunk, embed und generate."""

    parser = argparse.ArgumentParser(description="Minimal PDF ingestion and RAG pipeline.")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run")
    run.add_argument("pdf", nargs="?", default=DEFAULT_PDF)
    for name in ("extracted", "cleaned", "structured", "chunks", "chunks-markdown"):
        run.add_argument(f"--{name}-output", default=None)
    run.add_argument("--embeddings-output", default=None)
    run.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)

    extract_cmd = sub.add_parser("extract")
    extract_cmd.add_argument("pdf", nargs="?", default=DEFAULT_PDF)
    extract_cmd.add_argument("--output")

    clean_cmd = sub.add_parser("clean")
    clean_cmd.add_argument("source")
    clean_cmd.add_argument("--output")

    structure_cmd = sub.add_parser("structure")
    structure_cmd.add_argument("source")
    structure_cmd.add_argument("--output")

    chunk_cmd = sub.add_parser("chunk")
    chunk_cmd.add_argument("source")
    chunk_cmd.add_argument("--output")
    chunk_cmd.add_argument("--markdown-output")

    embed_cmd = sub.add_parser("embed")
    embed_cmd.add_argument("source", help="Path to a chunks JSON file.")
    embed_cmd.add_argument("--output")
    embed_cmd.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)

    retrieve_cmd = sub.add_parser("retrieve")
    retrieve_cmd.add_argument("query")
    retrieve_cmd.add_argument(
        "--embeddings",
        default=path_for(EMBEDDINGS, DEFAULT_PDF, ".npy"),
        help="Path to an embeddings .npy file.",
    )
    retrieve_cmd.add_argument("--top-k", type=int, default=5)
    retrieve_cmd.add_argument("--model", default=None)

    generate_cmd = sub.add_parser("generate")
    generate_cmd.add_argument("query")
    generate_cmd.add_argument("--mode", default="cheatsheet")
    generate_cmd.add_argument("--top-k", type=int, default=5)
    generate_cmd.add_argument("--min-score", type=float, default=0.5)
    generate_cmd.add_argument(
        "--embeddings",
        default=path_for(EMBEDDINGS, DEFAULT_PDF, ".npy"),
        help="Path to an embeddings .npy file.",
    )
    generate_cmd.add_argument("--embedding-model", default=None)
    generate_cmd.add_argument(
        "--provider",
        choices=("ollama", "openai"),
        default=os.environ.get("RAG_LLM_PROVIDER", "ollama"),
    )
    generate_cmd.add_argument("--llm-model", default=os.environ.get("RAG_LLM_MODEL"))
    generate_cmd.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL))
    generate_cmd.add_argument("--output", default=None)

    return parser.parse_args()


def main() -> None:
    """Führt je nach CLI-Befehl den passenden Pipeline-Schritt aus."""

    args = parse_args()
    ensure_output_dirs()

    if args.command == "extract":
        run_extract(args.pdf, args.output)
    elif args.command == "clean":
        run_clean(args.source, args.output)
    elif args.command == "structure":
        run_structure(args.source, args.output)
    elif args.command == "chunk":
        run_chunk(args.source, args.output, args.markdown_output)
    elif args.command == "embed":
        embed_chunks(args.source, args.output, args.model)
    elif args.command == "retrieve":
        print_results(retrieve_chunks(args.query, args.embeddings, args.top_k, args.model))
    elif args.command == "generate":
        generate_answer(
            args.query,
            args.embeddings,
            mode=args.mode,
            top_k=args.top_k,
            min_score=args.min_score,
            embedding_model=args.embedding_model,
            provider=args.provider,
            llm_model=args.llm_model,
            ollama_url=args.ollama_url,
            output=args.output,
        )
    else:
        run_all(getattr(args, "pdf", DEFAULT_PDF), args)
