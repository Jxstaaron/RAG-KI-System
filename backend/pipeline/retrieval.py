from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.pipeline.config import DEFAULT_EMBEDDING_MODEL
from backend.pipeline.embeddings import load_embedding_model
from backend.pipeline.io import read_json


def retrieve_chunks(
    query: str,
    embeddings_path: str | Path,
    top_k: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    import numpy as np

    embeddings_path = Path(embeddings_path)
    metadata_path = embeddings_path.with_name(f"{embeddings_path.stem}_metadata.json")
    metadata = read_json(metadata_path)
    model_name = model_name or metadata.get("model") or DEFAULT_EMBEDDING_MODEL

    model = load_embedding_model(model_name, local_files_only=True)
    vectors = np.load(embeddings_path)
    query_vector = model.encode(query, normalize_embeddings=True)
    scores = vectors @ query_vector

    results = []
    for index in np.argsort(scores)[::-1][:top_k]:
        chunk = metadata["chunks"][int(index)]
        results.append({**chunk, "score": float(scores[index])})
    return results


def print_results(results: list[dict[str, Any]]) -> None:
    for result in results:
        print(f"\nScore: {result['score']:.4f}")
        print(f"Chunk: {result['id']}")
        print(f"Heading: {result['heading'] or 'No heading'}")
        print(result["text"])
