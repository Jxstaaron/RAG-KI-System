from __future__ import annotations
"""Chunking: Aus strukturierten Textblöcken werden RAG-Einheiten gebaut."""

from backend.pipeline.tokenization import count_tokens, count_words


def join_blocks(blocks: list[dict]) -> str:
    """Fügt mehrere Textblocke mit Leerzeilen zusammen."""

    return "\n\n".join(block["text"] for block in blocks if block["text"].strip())


def take_words(text: str, count: int, end: bool = False) -> str:
    """Nimmt eine feste Anzahl Worter vom Anfang oder Ende eines Textes."""

    parts = text.split()
    return " ".join(parts[-count:] if end else parts[:count])


def chunk_blocks(
    blocks: list[dict],
    min_tokens: int = 200,
    max_tokens: int = 500,
    context_words: int = 50,
) -> list[dict]:
    """Erzeugt Chunks mit Zielgröße und etwas Kontext vor/nach dem Chunk."""

    content = [block for block in blocks if block["type"] != "heading"]
    chunks, current, current_tokens = [], [], 0

    def flush() -> None:
        """Speichert den aktuellen Chunk und leert den Zwischenspeicher."""

        nonlocal current, current_tokens
        if not current:
            return

        first = content.index(current[0])
        last = content.index(current[-1])
        core = join_blocks(current)
        # Kontext verbessert Retrieval, weil ein Chunk beim Embedding nicht völlig
        # isoliert betrachtet wird.
        before = take_words(join_blocks(content[:first]), context_words, end=True)
        after = take_words(join_blocks(content[last + 1 :]), context_words)
        text_with_context = "\n\n".join(part for part in (before, core, after) if part)

        chunks.append(
            {
                "id": len(chunks) + 1,
                "heading": current[0].get("heading"),
                "text": core,
                "token_count": count_tokens(core),
                "word_count": count_words(core),
                "block_start": current[0]["index"],
                "block_end": current[-1]["index"],
                "context_before": before,
                "context_after": after,
                "text_with_context": text_with_context,
            }
        )
        current, current_tokens = [], 0

    for block in content:
        block_tokens = block.get("token_count") or count_tokens(block["text"])
        if current and current_tokens >= min_tokens and current_tokens + block_tokens > max_tokens:
            flush()
        current.append(block)
        current_tokens += block_tokens
        if current_tokens >= max_tokens:
            flush()

    flush()
    return chunks


def chunks_to_markdown(chunks: list[dict]) -> str:
    """Erstellt eine lesbare Markdown-Vorschau der erzeugten Chunks."""

    parts = []
    for item in chunks:
        parts.append(
            f"# Chunk {item['id']}\n"
            f"Heading: {item['heading'] or 'No heading'}\n"
            f"Tokens: {item['token_count']}\n"
            f"Words: {item['word_count']}\n"
            f"Blocks: {item['block_start']}-{item['block_end']}\n\n"
            f"## Context before\n\n{item['context_before']}\n\n"
            f"## Text\n\n{item['text']}\n\n"
            f"## Context after\n\n{item['context_after']}\n"
        )
    return "\n\n---\n\n".join(parts)
