import re

from backend.ingestion.models import StructuredBlock
from backend.ingestion.tokenization import estimate_token_count


def is_heading(line: str) -> bool:
    stripped = line.strip()

    if stripped.startswith("#"):
        return True

    # Short title-like lines
    if (
        len(stripped) < 80
        and stripped[:1].isupper()
        and not stripped.endswith(".")
    ):
        return True

    return False


def is_list_item(line: str) -> bool:
    stripped = line.strip()

    return bool(
        re.match(r'^([-*•]|\d+\.)\s+', stripped)
    )


def split_paragraphs(text: str) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]


def recognize_structure(text: str) -> list[StructuredBlock]:
    """
    Detect headings and paragraphs with deterministic rules only.
    """

    blocks: list[StructuredBlock] = []
    current_heading: str | None = None

    for paragraph in split_paragraphs(text):
        paragraph_type = "heading" if is_heading(paragraph) else "paragraph"

        if paragraph_type == "heading":
            current_heading = paragraph.lstrip("#").strip()

        blocks.append(
            StructuredBlock(
                type=paragraph_type,
                text=paragraph,
                index=len(blocks),
                heading=current_heading if paragraph_type != "heading" else current_heading,
                token_count=estimate_token_count(paragraph),
            )
        )

    return blocks
