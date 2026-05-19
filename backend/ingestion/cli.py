import argparse
from pathlib import Path

from backend.ingestion.chunking import chunk_structured_blocks, chunks_to_markdown
from backend.ingestion.cleaners import clean_text
from backend.ingestion.io import read_json, read_text, save_json, save_text
from backend.ingestion.models import StructuredBlock
from backend.ingestion.paths import (
    PDF_INPUT_DIR,
    cleaned_text_path_for,
    chunks_markdown_path_for,
    chunks_path_for,
    ensure_data_dirs,
    extracted_text_path_for,
    structured_blocks_path_for,
)
from backend.ingestion.structure import recognize_structure

DEFAULT_PDF_PATH = PDF_INPUT_DIR / "file.pdf"


def run_extraction_stage(pdf_path: str | Path, extracted_output_path: str | Path | None = None, ) -> str:
    from backend.ingestion.extractors import extract_pdf

    pdf_path = Path(pdf_path)
    extracted_output_path = Path(extracted_output_path or extracted_text_path_for(pdf_path))

    print(f"Extracting PDF: {pdf_path}")

    raw_text = extract_pdf(str(pdf_path))

    save_text(raw_text, extracted_output_path)

    print(f"Saved extracted text to: {extracted_output_path}")

    return raw_text


def run_cleaning_stage(
        extracted_input_path: str | Path,
        cleaned_output_path: str | Path,
) -> str:
    print(f"Cleaning extracted text: {extracted_input_path}")

    raw_text = read_text(extracted_input_path)

    cleaned_text = clean_text(raw_text)

    save_text(cleaned_text, cleaned_output_path)

    print("\n========== CLEANED OUTPUT ==========\n")

    print(cleaned_text[:5000])

    print(f"\nSaved cleaned text to: {cleaned_output_path}")

    return cleaned_text


def run_structure_stage(
        cleaned_input_path: str | Path,
        structured_output_path: str | Path | None = None,
) -> list[StructuredBlock]:
    cleaned_input_path = Path(cleaned_input_path)
    structured_output_path = Path(
        structured_output_path or structured_blocks_path_for(cleaned_input_path)
    )

    print(f"Recognizing structure: {cleaned_input_path}")

    cleaned_text = read_text(cleaned_input_path)
    blocks = recognize_structure(cleaned_text)

    save_json([block.to_dict() for block in blocks], structured_output_path)

    heading_count = sum(1 for block in blocks if block.type == "heading")
    paragraph_count = sum(1 for block in blocks if block.type == "paragraph")

    print(f"Saved structured blocks to: {structured_output_path}")
    print(f"Headings: {heading_count}")
    print(f"Paragraphs: {paragraph_count}")

    return blocks


def run_chunking_stage(
        structured_input_path: str | Path,
        chunks_output_path: str | Path | None = None,
        chunks_markdown_output_path: str | Path | None = None,
        min_tokens: int = 500,
        max_tokens: int = 800,
        context_words: int = 100,
):
    structured_input_path = Path(structured_input_path)
    chunks_output_path = Path(chunks_output_path or chunks_path_for(structured_input_path))
    chunks_markdown_output_path = Path(
        chunks_markdown_output_path or chunks_markdown_path_for(structured_input_path)
    )

    print(f"Creating chunks from structured blocks: {structured_input_path}")

    blocks = [
        StructuredBlock.from_dict(block)
        for block in read_json(structured_input_path)
    ]
    chunks = chunk_structured_blocks(
        blocks,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        context_words=context_words,
    )

    save_json([chunk.to_dict() for chunk in chunks], chunks_output_path)
    save_text(chunks_to_markdown(chunks), chunks_markdown_output_path)

    print(f"Saved chunks JSON to: {chunks_output_path}")
    print(f"Saved chunks Markdown to: {chunks_markdown_output_path}")
    print(f"Chunks created: {len(chunks)}")

    return chunks


def run_pipeline(
        pdf_path: str | Path = DEFAULT_PDF_PATH,
        extracted_output_path: str | Path | None = None,
        cleaned_output_path: str | Path | None = None,
        structured_output_path: str | Path | None = None,
        chunks_output_path: str | Path | None = None,
        chunks_markdown_output_path: str | Path | None = None,
) -> str:
    ensure_data_dirs()

    pdf_path = Path(pdf_path)
    extracted_output_path = Path(extracted_output_path or extracted_text_path_for(pdf_path))
    cleaned_output_path = Path(cleaned_output_path or cleaned_text_path_for(pdf_path))
    structured_output_path = Path(
        structured_output_path or structured_blocks_path_for(cleaned_output_path)
    )
    chunks_output_path = Path(chunks_output_path or chunks_path_for(structured_output_path))
    chunks_markdown_output_path = Path(
        chunks_markdown_output_path or chunks_markdown_path_for(structured_output_path)
    )

    run_extraction_stage(pdf_path, extracted_output_path)

    cleaned_text = run_cleaning_stage(extracted_output_path, cleaned_output_path)

    run_structure_stage(cleaned_output_path, structured_output_path)

    run_chunking_stage(
        structured_output_path,
        chunks_output_path,
        chunks_markdown_output_path,
    )

    return cleaned_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract raw text from a PDF, then clean it for downstream RAG use."
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Extract a PDF and then clean the extracted text.",
    )
    run_parser.add_argument(
        "pdf_path",
        nargs="?",
        default=DEFAULT_PDF_PATH,
        help=f"PDF to process. Defaults to {DEFAULT_PDF_PATH}.",
    )
    run_parser.add_argument(
        "--extracted-output",
        default=None,
        help="Where to save the raw extracted Markdown/text.",
    )
    run_parser.add_argument(
        "--cleaned-output",
        default=None,
        help="Where to save the cleaned text.",
    )
    run_parser.add_argument(
        "--structured-output",
        default=None,
        help="Where to save the detected heading/paragraph blocks JSON.",
    )
    run_parser.add_argument(
        "--chunks-output",
        default=None,
        help="Where to save the chunks JSON.",
    )
    run_parser.add_argument(
        "--chunks-markdown-output",
        default=None,
        help="Where to save a human-readable chunks Markdown preview.",
    )

    extract_parser = subparsers.add_parser(
        "extract",
        help="Only extract raw Markdown/text from a PDF.",
    )
    extract_parser.add_argument(
        "pdf_path",
        nargs="?",
        default=DEFAULT_PDF_PATH,
        help=f"PDF to extract. Defaults to {DEFAULT_PDF_PATH}.",
    )
    extract_parser.add_argument(
        "--output",
        default=None,
        help="Where to save the raw extracted Markdown/text.",
    )

    clean_parser = subparsers.add_parser(
        "clean",
        help="Only clean a previously extracted text file.",
    )
    clean_parser.add_argument(
        "extracted_input",
        help="Raw extracted Markdown/text file to clean.",
    )
    clean_parser.add_argument(
        "--output",
        default=None,
        help="Where to save the cleaned text.",
    )

    structure_parser = subparsers.add_parser(
        "structure",
        help="Detect headings and paragraphs from cleaned text.",
    )
    structure_parser.add_argument(
        "cleaned_input",
        help="Cleaned text file to structure.",
    )
    structure_parser.add_argument(
        "--output",
        default=None,
        help="Where to save structured block JSON.",
    )

    chunk_parser = subparsers.add_parser(
        "chunk",
        help="Create algorithmic chunks from structured block JSON.",
    )
    chunk_parser.add_argument(
        "structured_input",
        help="Structured block JSON file to chunk.",
    )
    chunk_parser.add_argument(
        "--output",
        default=None,
        help="Where to save chunks JSON.",
    )
    chunk_parser.add_argument(
        "--markdown-output",
        default=None,
        help="Where to save a human-readable chunks Markdown preview.",
    )
    chunk_parser.add_argument(
        "--min-tokens",
        type=int,
        default=500,
        help="Target minimum tokens per chunk.",
    )
    chunk_parser.add_argument(
        "--max-tokens",
        type=int,
        default=800,
        help="Target maximum tokens per chunk.",
    )
    chunk_parser.add_argument(
        "--context-words",
        type=int,
        default=100,
        help="Number of words to include from before and after each chunk.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.command == "extract":
        ensure_data_dirs()
        run_extraction_stage(args.pdf_path, args.output)
        return

    if args.command == "clean":
        ensure_data_dirs()
        output_path = args.output or cleaned_text_path_for(args.extracted_input)
        run_cleaning_stage(args.extracted_input, output_path)
        return

    if args.command == "structure":
        ensure_data_dirs()
        run_structure_stage(args.cleaned_input, args.output)
        return

    if args.command == "chunk":
        ensure_data_dirs()
        run_chunking_stage(
            args.structured_input,
            args.output,
            args.markdown_output,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
            context_words=args.context_words,
        )
        return

    run_pipeline(
        pdf_path=getattr(args, "pdf_path", DEFAULT_PDF_PATH),
        extracted_output_path=getattr(args, "extracted_output", None),
        cleaned_output_path=getattr(args, "cleaned_output", None),
        structured_output_path=getattr(args, "structured_output", None),
        chunks_output_path=getattr(args, "chunks_output", None),
        chunks_markdown_output_path=getattr(args, "chunks_markdown_output", None),
    )


if __name__ == "__main__":
    main()
