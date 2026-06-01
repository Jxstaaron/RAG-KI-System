from __future__ import annotations

import argparse
import json
import re
import unicodedata
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "backend" / "data"
PDFS = DATA / "pdfs"
EXTRACTED = DATA / "extracted_text"
CLEANED = DATA / "cleaned_text"
STRUCTURED = DATA / "structured_blocks"
CHUNKS = DATA / "chunks"
DEFAULT_PDF = PDFS / "file.pdf"

def out_dir() -> None:
    for path in (PDFS, EXTRACTED, CLEANED, STRUCTURED, CHUNKS):
        path.mkdir(parents=True, exist_ok=True)

def path_for(folder: Path, source: str | Path, suffix: str) -> Path:
    return folder / f"{Path(source).stem}{suffix}"

def read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")

def write(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def write_json(path: str | Path, data) -> None:
    write(path, json.dumps(data, ensure_ascii=False, indent=2))

def tokens(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))

def words(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))

def heading(line: str) -> bool:
    line = line.strip()
    return line.startswith("#") or (
        len(line) < 80 and line[:1].isupper() and not line.endswith(".")
    )

def list_item(line: str) -> bool:
    return bool(re.match(r"^([-*•]|\d+\.)\s+", line.strip()))

def extract(pdf: str | Path) -> str:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    return PdfConverter(artifact_dict=create_model_dict())(str(pdf)).markdown

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
        if not line or heading(line) or list_item(line) or line.startswith("!["):
            merged.append(line)
        elif merged and merged[-1] and not heading(merged[-1]):
            merged[-1] += f" {line}"
        else:
            merged.append(line)
    return "\n".join(merged)

def clean(text: str) -> str:
    text = fix_encoding(text)
    text = re.sub(r"!\[\]\(.*?\)", "", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"(\d+)\s*°\s*C", r"\1°C", text)
    text = re.sub(r"\bM\d+\*?\b|Seite\s+\d+|Page\s+\d+", "", text, flags=re.I)
    noise = (
        r"^\s*[\d\s.,%$€-]+\s*$|"
        r"©|WTO|EX|"
        r"^\s*[A-Z0-9]{6,}\s*$"
    )
    text = "\n".join(line for line in text.splitlines() if not re.search(noise, line))
    text = merge_lines(text)
    for char in "äöüÄÖÜ":
        text = re.sub(rf"\b([A-Za-z]{{1,2}})\s+{char}", rf"\1{char}", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def structure(text: str) -> list[dict]:
    blocks = []
    current_heading = None
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        block_type = "heading" if heading(paragraph) else "paragraph"
        if block_type == "heading":
            current_heading = paragraph.lstrip("#").strip()
        blocks.append(
            {
                "type": block_type,
                "text": paragraph,
                "index": len(blocks),
                "heading": current_heading,
                "token_count": tokens(paragraph),
            }
        )

    return blocks

def join(blocks: list[dict]) -> str:
    return "\n\n".join(block["text"] for block in blocks if block["text"].strip())

def take(text: str, count: int, end: bool = False) -> str:
    parts = text.split()
    return " ".join(parts[-count:] if end else parts[:count])

def chunk(blocks: list[dict], min_tokens: int = 200, max_tokens: int = 500, context_words: int = 50) -> list[dict]:
    content = [block for block in blocks if block["type"] != "heading"]
    chunks, current, current_tokens = [], [], 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        first = content.index(current[0])
        last = content.index(current[-1])
        core = join(current)
        before = take(join(content[:first]), context_words, end=True)
        after = take(join(content[last + 1:]), context_words)
        text_with_context = "\n\n".join(part for part in (before, core, after) if part)

        chunks.append(
            {
                "id": len(chunks) + 1,
                "heading": current[0].get("heading"),
                "text": core,
                "token_count": tokens(core),
                "word_count": words(core),
                "block_start": current[0]["index"],
                "block_end": current[-1]["index"],
                "context_before": before,
                "context_after": after,
                "text_with_context": text_with_context,
            }
        )
        current, current_tokens = [], 0

    for block in content:
        block_tokens = block.get("token_count") or tokens(block["text"])
        if current and current_tokens >= min_tokens and current_tokens + block_tokens > max_tokens:
            flush()
        current.append(block)
        current_tokens += block_tokens
        if current_tokens >= max_tokens:
            flush()
    flush()
    return chunks

def chunks_md(chunks: list[dict]) -> str:
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

def run_extract(pdf: str | Path, output: str | Path | None = None) -> str:
    output = output or path_for(EXTRACTED, pdf, ".md")
    print(f"Extracting PDF: {pdf}")
    text = extract(pdf)
    write(output, text)
    print(f"Saved extracted text to: {output}")
    return text

def run_clean(source: str | Path, output: str | Path | None = None) -> str:
    output = output or path_for(CLEANED, source, ".txt")
    text = clean(read(source))
    write(output, text)
    print(f"Saved cleaned text to: {output}")
    return text

def run_structure(source: str | Path, output: str | Path | None = None) -> list[dict]:
    output = output or path_for(STRUCTURED, source, ".json")
    blocks = structure(read(source))
    write_json(output, blocks)
    print(f"Saved {len(blocks)} structured blocks to: {output}")
    return blocks

def run_chunk(source: str | Path, output: str | Path | None = None, markdown: str | Path | None = None) -> list[dict]:
    output = output or path_for(CHUNKS, source, ".json")
    markdown = markdown or path_for(CHUNKS, source, ".md")
    chunks = chunk(json.loads(read(source)))
    write_json(output, chunks)
    write(markdown, chunks_md(chunks))
    print(f"Saved {len(chunks)} chunks to: {output}")
    print(f"Saved chunk preview to: {markdown}")
    return chunks

def run_all(pdf: str | Path, args: argparse.Namespace) -> None:
    extracted = getattr(args, "extracted_output", None) or path_for(EXTRACTED, pdf, ".md")
    cleaned = getattr(args, "cleaned_output", None) or path_for(CLEANED, pdf, ".txt")
    structured = getattr(args, "structured_output", None) or path_for(STRUCTURED, cleaned, ".json")
    chunks = getattr(args, "chunks_output", None) or path_for(CHUNKS, structured, ".json")
    chunks_markdown = getattr(args, "chunks_markdown_output", None) or path_for(CHUNKS, structured, ".md")

    run_extract(pdf, extracted)
    run_clean(extracted, cleaned)
    run_structure(cleaned, structured)
    run_chunk(structured, chunks, chunks_markdown)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal PDF ingestion pipeline.")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run")
    run.add_argument("pdf", nargs="?", default=DEFAULT_PDF)
    for name in ("extracted", "cleaned", "structured", "chunks", "chunks-markdown"):
        run.add_argument(f"--{name}-output", default=None)

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

    return parser.parse_args()

def main() -> None:
    args = parse_args()
    out_dir()

    if args.command == "extract":
        run_extract(args.pdf, args.output)
    elif args.command == "clean":
        run_clean(args.source, args.output)
    elif args.command == "structure":
        run_structure(args.source, args.output)
    elif args.command == "chunk":
        run_chunk(args.source, args.output, args.markdown_output)
    else:
        run_all(getattr(args, "pdf", DEFAULT_PDF), args)

if __name__ == "__main__":
    main()