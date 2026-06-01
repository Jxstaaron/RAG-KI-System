from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.pipeline.config import DEFAULT_EMBEDDING_MODEL, EMBEDDINGS, path_for
from backend.pipeline.io import read_json, write_json


def local_model_path(model_name: str) -> str | None:
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    candidates = [model_name]
    if "/" not in model_name:
        candidates.append(f"sentence-transformers/{model_name}")

    for candidate in candidates:
        model_dir = cache_root / f"models--{candidate.replace('/', '--')}"
        refs_main = model_dir / "refs" / "main"
        if refs_main.exists():
            snapshot = model_dir / "snapshots" / refs_main.read_text(encoding="utf-8").strip()
            if snapshot.exists():
                return str(snapshot)

        snapshots = model_dir / "snapshots"
        if snapshots.exists():
            available = sorted(path for path in snapshots.iterdir() if path.is_dir())
            if available:
                return str(available[-1])
    return None


def load_embedding_model(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    local_files_only: bool = False,
):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: sentence-transformers. "
            "Install it with `pip install sentence-transformers`."
        ) from exc

    if local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        model_name = local_model_path(model_name) or model_name
    return SentenceTransformer(model_name, local_files_only=local_files_only)


def embedding_paths(source: str | Path, output: str | Path | None = None) -> tuple[Path, Path]:
    vectors = Path(output) if output else path_for(EMBEDDINGS, source, ".npy")
    metadata = vectors.with_name(f"{vectors.stem}_metadata.json")
    return vectors, metadata


def text_for_embedding(chunk: dict[str, Any]) -> str:
    return chunk.get("text_with_context") or chunk["text"]


def metadata_for_chunk(chunk: dict[str, Any], source: str | Path, model_name: str) -> dict[str, Any]:
    return {
        "id": chunk["id"],
        "source": str(source),
        "embedding_model": model_name,
        "heading": chunk.get("heading"),
        "text": chunk["text"],
        "token_count": chunk.get("token_count"),
        "word_count": chunk.get("word_count"),
        "block_start": chunk.get("block_start"),
        "block_end": chunk.get("block_end"),
    }


def embed_chunks(
    source: str | Path,
    output: str | Path | None = None,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> None:
    import numpy as np

    chunks = read_json(source)
    if not chunks:
        raise SystemExit(f"No chunks found in: {source}")

    model = load_embedding_model(model_name)
    vectors = model.encode(
        [text_for_embedding(item) for item in chunks],
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    vectors_path, metadata_path = embedding_paths(source, output)
    vectors_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vectors_path, vectors)
    write_json(
        metadata_path,
        {
            "model": model_name,
            "source": str(source),
            "count": len(chunks),
            "dimensions": int(vectors.shape[1]),
            "chunks": [metadata_for_chunk(item, source, model_name) for item in chunks],
        },
    )
    print(f"Saved {len(chunks)} embeddings to: {vectors_path}")
    print(f"Saved embedding metadata to: {metadata_path}")
