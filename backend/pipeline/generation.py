from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from backend.pipeline.config import (
    DEFAULT_LLM_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
)
from backend.pipeline.io import write_text
from backend.pipeline.retrieval import retrieve_chunks


def mode_instruction(mode: str) -> str:
    instructions = {
        "cheatsheet": (
            "Erstelle einen kompakten Spickzettel mit den wichtigsten Begriffen, "
            "Zusammenhaengen und Fakten. Nutze kurze Ueberschriften und Stichpunkte."
        ),
        "summary": "Fasse die wichtigsten Inhalte knapp und verstaendlich zusammen.",
        "quiz": (
            "Erstelle Lernfragen mit kurzen Musterantworten. Mische Verstaendnisfragen "
            "und Faktenfragen."
        ),
        "flashcards": "Erstelle Karteikarten im Format 'Frage: ...' und 'Antwort: ...'.",
        "explanation": (
            "Erklaere das Thema einfach und schuelerfreundlich, aber sachlich korrekt."
        ),
    }
    if mode not in instructions:
        valid = ", ".join(sorted(instructions))
        raise SystemExit(f"Unknown mode: {mode}. Choose one of: {valid}")
    return instructions[mode]


def build_prompt(query: str, chunks: list[dict[str, Any]], mode: str) -> str:
    context_parts = []
    for number, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Chunk {number} | id={chunk['id']} | score={chunk.get('score', 0.0):.4f}]\n"
            f"Heading: {chunk.get('heading') or 'No heading'}\n"
            f"{chunk['text']}"
        )

    context = "\n\n---\n\n".join(context_parts)
    return (
        "Du bist ein Lernassistent fuer ein Schulprojekt.\n"
        "Nutze ausschliesslich die bereitgestellten Kontext-Chunks.\n"
        "Wenn die Chunks nicht genug Informationen enthalten, sage das klar.\n"
        "Erfinde keine Fakten und antworte auf Deutsch.\n"
        "Nutze kein Allgemeinwissen ausserhalb der Chunks.\n"
        "Erwaehne nur Begriffe, Ursachen, Folgen und Beispiele, die in den Chunks vorkommen.\n"
        "Wenn ein moeglicher Punkt nicht direkt aus den Chunks belegbar ist, lasse ihn weg.\n\n"
        f"Aufgabe:\n{mode_instruction(mode)}\n\n"
        f"User-Anfrage:\n{query}\n\n"
        f"Kontext-Chunks:\n{context}\n"
    )


def call_openai(prompt: str, model_name: str = DEFAULT_LLM_MODEL) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing OPENAI_API_KEY. Set it before running generate, for example: "
            "`export OPENAI_API_KEY=your_api_key_here`."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Missing dependency: openai. Install it with `pip install openai`.") from exc

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "Du beantwortest Aufgaben nur anhand des gegebenen RAG-Kontexts.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def call_ollama(
    prompt: str,
    model_name: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> str:
    payload = json.dumps(
        {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(
            "Could not connect to Ollama. Make sure the Ollama app/server is running, "
            f"then try again. URL: {base_url}"
        ) from exc

    if "error" in data:
        raise SystemExit(f"Ollama error: {data['error']}")
    return data.get("response", "")


def call_llm(prompt: str, provider: str, model_name: str, ollama_url: str) -> str:
    if provider == "ollama":
        return call_ollama(prompt, model_name, ollama_url)
    if provider == "openai":
        return call_openai(prompt, model_name)
    raise SystemExit("Unknown provider. Choose one of: ollama, openai")


def generate_answer(
    query: str,
    embeddings_path: str | Path,
    mode: str = "cheatsheet",
    top_k: int = 5,
    min_score: float = 0.5,
    embedding_model: str | None = None,
    provider: str = "ollama",
    llm_model: str | None = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    output: str | Path | None = None,
) -> str:
    chunks = retrieve_chunks(query, embeddings_path, top_k=top_k, model_name=embedding_model)
    chunks = [chunk for chunk in chunks if chunk.get("score", 0.0) >= min_score]
    if not chunks:
        answer = (
            "Die gespeicherten Chunks enthalten nicht genug passende Informationen "
            f"fuer diese Anfrage. Hoechster Treffer liegt unter min_score={min_score}."
        )
    else:
        model = llm_model or (DEFAULT_OLLAMA_MODEL if provider == "ollama" else DEFAULT_LLM_MODEL)
        answer = call_llm(build_prompt(query, chunks, mode), provider, model, ollama_url)

    if output:
        write_text(output, answer)
        print(f"Saved generated answer to: {output}")
    else:
        print(answer)
    return answer
