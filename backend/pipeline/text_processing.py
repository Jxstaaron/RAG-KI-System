from __future__ import annotations

import re
import unicodedata
import warnings

from backend.pipeline.tokenization import count_tokens


def is_heading(line: str) -> bool:
    line = line.strip()
    return line.startswith("#") or (
        len(line) < 80 and line[:1].isupper() and not line.endswith(".")
    )


def is_list_item(line: str) -> bool:
    return bool(re.match(r"^([-*•]|\d+\.)\s+", line.strip()))


def fix_encoding(text: str) -> str:
    if re.search(r"\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}", text):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                text = text.encode().decode("unicode_escape")
        except Exception:
            pass

    try:
        from ftfy import fix_text

        text = fix_text(text)
    except Exception:
        for bad, good in {
            "Ã¤": "ä",
            "Ã¶": "ö",
            "Ã¼": "ü",
            "Ã„": "Ä",
            "Ã–": "Ö",
            "Ãœ": "Ü",
            "ÃŸ": "ß",
            "Â°": "°",
            "Â": "",
        }.items():
            text = text.replace(bad, good)
    return unicodedata.normalize("NFKC", text)


def merge_lines(text: str) -> str:
    merged: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or is_heading(line) or is_list_item(line) or line.startswith("!["):
            merged.append(line)
        elif merged and merged[-1] and not is_heading(merged[-1]):
            merged[-1] += f" {line}"
        else:
            merged.append(line)
    return "\n".join(merged)


def clean_text(text: str) -> str:
    text = fix_encoding(text)
    text = re.sub(r"!\[\]\(.*?\)", "", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"(\d+)\s*°\s*C", r"\1°C", text)
    text = re.sub(r"\bM\d+\*?\b|Seite\s+\d+|Page\s+\d+", "", text, flags=re.I)
    noise = r"^\s*[\d\s.,%$€-]+\s*$|©|WTO|EX|^\s*[A-Z0-9]{6,}\s*$"
    text = "\n".join(line for line in text.splitlines() if not re.search(noise, line))
    text = merge_lines(text)

    for char in "äöüÄÖÜ":
        text = re.sub(rf"\b([A-Za-z]{{1,2}})\s+{char}", rf"\1{char}", text)

    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def structure_text(text: str) -> list[dict]:
    blocks = []
    current_heading = None
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        block_type = "heading" if is_heading(paragraph) else "paragraph"
        if block_type == "heading":
            current_heading = paragraph.lstrip("#").strip()
        blocks.append(
            {
                "type": block_type,
                "text": paragraph,
                "index": len(blocks),
                "heading": current_heading,
                "token_count": count_tokens(paragraph),
            }
        )
    return blocks
