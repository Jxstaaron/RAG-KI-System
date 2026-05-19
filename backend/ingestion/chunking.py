from backend.ingestion.models import Chunk, StructuredBlock
from backend.ingestion.tokenization import count_words, estimate_token_count


def take_first_words(text: str, word_count: int) -> str:
    words = text.split()
    return " ".join(words[:word_count])


def take_last_words(text: str, word_count: int) -> str:
    words = text.split()
    return " ".join(words[-word_count:])


def join_block_texts(blocks: list[StructuredBlock]) -> str:
    return "\n\n".join(block.text for block in blocks if block.text.strip())


def build_text_with_context(
    context_before: str,
    text: str,
    context_after: str,
) -> str:
    parts = []

    if context_before:
        parts.append(context_before)

    parts.append(text)

    if context_after:
        parts.append(context_after)

    return "\n\n".join(parts)


def chunk_structured_blocks(
    blocks: list[StructuredBlock],
    min_tokens: int = 500,
    max_tokens: int = 800,
    context_words: int = 100,
) -> list[Chunk]:
    """
    Build algorithmic chunks from structured paragraph/heading blocks.

    Headings are kept as metadata and paragraphs/lists are grouped until the
    chunk reaches the target token range. Neighbor context is added separately
    so retrieval can use the core chunk or the expanded text.
    """

    content_blocks = [block for block in blocks if block.type != "heading"]
    chunks: list[Chunk] = []
    current_blocks: list[StructuredBlock] = []
    current_tokens = 0

    def flush():
        nonlocal current_blocks, current_tokens

        if not current_blocks:
            return

        core_text = join_block_texts(current_blocks)
        previous_text = join_block_texts(content_blocks[:content_blocks.index(current_blocks[0])])
        next_start_index = content_blocks.index(current_blocks[-1]) + 1
        next_text = join_block_texts(content_blocks[next_start_index:])
        context_before = take_last_words(previous_text, context_words)
        context_after = take_first_words(next_text, context_words)
        heading = current_blocks[0].heading

        chunks.append(
            Chunk(
                id=len(chunks) + 1,
                heading=heading,
                text=core_text,
                token_count=estimate_token_count(core_text),
                word_count=count_words(core_text),
                block_start=current_blocks[0].index,
                block_end=current_blocks[-1].index,
                context_before=context_before,
                context_after=context_after,
                text_with_context=build_text_with_context(
                    context_before,
                    core_text,
                    context_after,
                ),
            )
        )

        current_blocks = []
        current_tokens = 0

    for block in content_blocks:
        block_tokens = block.token_count or estimate_token_count(block.text)
        would_exceed_max = current_blocks and current_tokens + block_tokens > max_tokens
        reached_minimum = current_tokens >= min_tokens

        if would_exceed_max and reached_minimum:
            flush()

        current_blocks.append(block)
        current_tokens += block_tokens

        if current_tokens >= max_tokens:
            flush()

    flush()

    return chunks


def chunks_to_markdown(chunks: list[Chunk]) -> str:
    output = []

    for chunk in chunks:
        heading = chunk.heading or "No heading"
        output.append(
            f"# Chunk {chunk.id}\n"
            f"Heading: {heading}\n"
            f"Tokens: {chunk.token_count}\n"
            f"Words: {chunk.word_count}\n"
            f"Blocks: {chunk.block_start}-{chunk.block_end}\n\n"
            f"## Context before\n\n"
            f"{chunk.context_before}\n\n"
            f"## Text\n\n"
            f"{chunk.text}\n\n"
            f"## Context after\n\n"
            f"{chunk.context_after}\n"
        )

    return "\n\n---\n\n".join(output)
