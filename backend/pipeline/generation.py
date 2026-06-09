from __future__ import annotations
"""Antwortgenerierung mit Retrieval-Kontext und lokalem/externem LLM."""

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
    """Liefert die genaue Arbeitsanweisung für den gewählten Modus."""

    instructions = {
        "cheatsheet": (
            "Erstelle einen kompakten Spickzettel mit den wichtigsten Begriffen, "
            "Zusammenhängen und Fakten. Nutze kurze Überschriften und Stichpunkte."
        ),
        "summary": "Fasse die wichtigsten Inhalte knapp und verständlich zusammen.",
        "quiz": (
            "Erstelle Lernfragen mit kurzen Musterantworten. Mische Verständnisfragen "
            "und Faktenfragen."
        ),
        "flashcards": "Erstelle Karteikarten im Format 'Frage: ...' und 'Antwort: ...'.",
        "explanation": (
            "Erkläre das Thema einfach und schülerfreundlich, aber sachlich korrekt."
        ),
        "custom": (
            "Beantworte die User-Anfrage direkt und verständlich anhand der passenden "
            "Kontext-Chunks."
        ),
    }
    if mode not in instructions:
        valid = ", ".join(sorted(instructions))
        raise SystemExit(f"Unknown mode: {mode}. Choose one of: {valid}")
    return instructions[mode]


def build_prompt(query: str, chunks: list[dict[str, Any]], mode: str) -> str:
    """Baut den finalen Prompt aus Aufgabe, User-Frage und RAG-Kontext."""

    context_parts = []
    for number, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Chunk {number} | id={chunk['id']} | score={chunk.get('score', 0.0):.4f}]\n"
            f"Heading: {chunk.get('heading') or 'No heading'}\n"
            f"{chunk['text']}"
        )

    # Der Prompt verbietet bewusst Allgemeinwissen, damit Antworten nur aus den
    # gefundenen PDF-Chunks entstehen.
    return (
        "Du bist ein Lernassistent für ein Schulprojekt.\n"
        "Nutze ausschließlich die bereitgestellten Kontext-Chunks.\n"
        "Wenn die Chunks nicht genug Informationen enthalten, sage das klar.\n"
        "Erfinde keine Fakten und antworte auf Deutsch.\n"
        "Nutze kein Allgemeinwissen außerhalb der Chunks.\n"
        "Erwähne nur Begriffe, Ursachen, Folgen und Beispiele, die in den Chunks vorkommen.\n"
        "Wenn ein möglicher Punkt nicht direkt aus den Chunks belegbar ist, lasse ihn weg.\n\n"
        f"Aufgabe:\n{mode_instruction(mode)}\n\n"
        f"User-Anfrage:\n{query}\n\n"
        f"Kontext-Chunks:\n{chr(10).join(context_parts)}\n"
    )


def call_openai(prompt: str, model_name: str = DEFAULT_LLM_MODEL) -> str:
    """Optionaler OpenAI-Provider, falls ein API-Key gesetzt ist."""

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
    """Ruft ein lokal laufendes Ollama-Modell über dessen HTTP-API auf."""

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
    """Wählt anhand des Provider-Namens das passende LLM-Backend."""

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
    """Generiert eine Antwort auf Basis der passendsten Chunks."""

    chunks = retrieve_chunks(query, embeddings_path, top_k=top_k, model_name=embedding_model)
    chunks = [chunk for chunk in chunks if chunk.get("score", 0.0) >= min_score]
    if not chunks:
        # Bei zu geringer Ähnlichkeit wird keine Antwort erfunden.
        answer = (
            "Die gespeicherten Chunks enthalten nicht genug passende Informationen "
            f"für diese Anfrage. Hoechster Treffer liegt unter min_score={min_score}."
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


def generate_from_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    mode: str = "cheatsheet",
    provider: str = "ollama",
    llm_model: str | None = None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    output: str | Path | None = None,
) -> str:
    """Generiert eine Antwort aus allen Chunks, z.B. für Zusammenfassung/Quiz."""

    selected = [
        {
            **chunk,
            "score": 1.0,
            "text": chunk.get("text_with_context") or chunk["text"],
        }
        for chunk in chunks
    ]
    if not selected:
        answer = "Es wurden keine Chunks gefunden. Bitte lade zuerst ein PDF hoch."
    else:
        model = llm_model or (DEFAULT_OLLAMA_MODEL if provider == "ollama" else DEFAULT_LLM_MODEL)
        answer = call_llm(build_prompt(query, selected, mode), provider, model, ollama_url)

    if output:
        write_text(output, answer)
        print(f"Saved generated answer to: {output}")
    else:
        print(answer)
    return answer
