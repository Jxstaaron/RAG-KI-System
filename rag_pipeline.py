from __future__ import annotations
from pathlib import Path
import argparse
import os
import json
from typing import Any
import re
import unicodedata
import warnings
import urllib.error
import urllib.request

# ---- config.py ----

ROOT = Path.cwd()
DATA = ROOT / "data"
PDFS = DATA / "pdfs"
EXTRACTED = DATA / "extracted_text"
CLEANED = DATA / "cleaned_text"
STRUCTURED = DATA / "structured_blocks"
CHUNKS = DATA / "chunks"
EMBEDDINGS = DATA / "embeddings"

DEFAULT_PDF = PDFS / "file.pdf"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

def ensure_output_dirs() -> None:
    for path in (PDFS, EXTRACTED, CLEANED, STRUCTURED, CHUNKS, EMBEDDINGS):
        path.mkdir(parents=True, exist_ok=True)

def path_for(folder: Path, source: str | Path, suffix: str) -> Path:
    return folder / f"{Path(source).stem}{suffix}"

# ---- io.py ----

def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")

def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def read_json(path: str | Path) -> Any:
    return json.loads(read_text(path))

def write_json(path: str | Path, data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))

# ---- tokenization.py ----

def count_tokens(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))

def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))

# ---- extraction.py ----

def extract_pdf(pdf: str | Path) -> str:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    return PdfConverter(artifact_dict=create_model_dict())(str(pdf)).markdown

# ---- text_processing.py ----

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

# ---- chunking.py ----

def join_blocks(blocks: list[dict]) -> str:
    return "\n\n".join(block["text"] for block in blocks if block["text"].strip())

def take_words(text: str, count: int, end: bool = False) -> str:
    parts = text.split()
    return " ".join(parts[-count:] if end else parts[:count])

def chunk_blocks(
    blocks: list[dict],
    min_tokens: int = 200,
    max_tokens: int = 500,
    context_words: int = 50,
) -> list[dict]:
    content = [block for block in blocks if block["type"] != "heading"]
    chunks, current, current_tokens = [], [], 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return

        first = content.index(current[0])
        last = content.index(current[-1])
        core = join_blocks(current)
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

# ---- embeddings(1).py ----

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

# ---- retrieval.py ----

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

# ---- generation.py ----

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
        f"Kontext-Chunks:\n{chr(10).join(context_parts)}\n"
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

# ---- stages.py ----

def run_extract(pdf: str | Path, output: str | Path | None = None) -> str:
    output = output or path_for(EXTRACTED, pdf, ".md")
    print(f"Extracting PDF: {pdf}")
    text = extract_pdf(pdf)
    write_text(output, text)
    print(f"Saved extracted text to: {output}")
    return text

def run_clean(source: str | Path, output: str | Path | None = None) -> str:
    output = output or path_for(CLEANED, source, ".txt")
    text = clean_text(read_text(source))
    write_text(output, text)
    print(f"Saved cleaned text to: {output}")
    return text

def run_structure(source: str | Path, output: str | Path | None = None) -> list[dict]:
    output = output or path_for(STRUCTURED, source, ".json")
    blocks = structure_text(read_text(source))
    write_json(output, blocks)
    print(f"Saved {len(blocks)} structured blocks to: {output}")
    return blocks

def run_chunk(
    source: str | Path,
    output: str | Path | None = None,
    markdown: str | Path | None = None,
) -> list[dict]:
    output = output or path_for(CHUNKS, source, ".json")
    markdown = markdown or path_for(CHUNKS, source, ".md")
    chunks = chunk_blocks(read_json(source))
    write_json(output, chunks)
    write_text(markdown, chunks_to_markdown(chunks))
    print(f"Saved {len(chunks)} chunks to: {output}")
    print(f"Saved chunk preview to: {markdown}")
    return chunks

def run_all(pdf: str | Path, args: argparse.Namespace) -> None:
    extracted = getattr(args, "extracted_output", None) or path_for(EXTRACTED, pdf, ".md")
    cleaned = getattr(args, "cleaned_output", None) or path_for(CLEANED, pdf, ".txt")
    structured = getattr(args, "structured_output", None) or path_for(STRUCTURED, cleaned, ".json")
    chunks = getattr(args, "chunks_output", None) or path_for(CHUNKS, structured, ".json")
    chunks_markdown = getattr(args, "chunks_markdown_output", None) or path_for(CHUNKS, structured, ".md")
    embeddings = getattr(args, "embeddings_output", None) or path_for(EMBEDDINGS, chunks, ".npy")
    embedding_model = getattr(args, "embedding_model", DEFAULT_EMBEDDING_MODEL)

    run_extract(pdf, extracted)
    run_clean(extracted, cleaned)
    run_structure(cleaned, structured)
    run_chunk(structured, chunks, chunks_markdown)
    embed_chunks(chunks, embeddings, embedding_model)

# ---- cli.py ----

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal PDF ingestion and RAG pipeline.")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run")
    run.add_argument("pdf", nargs="?", default=DEFAULT_PDF)
    for name in ("extracted", "cleaned", "structured", "chunks", "chunks-markdown"):
        run.add_argument(f"--{name}-output", default=None)
    run.add_argument("--embeddings-output", default=None)
    run.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)

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

    embed_cmd = sub.add_parser("embed")
    embed_cmd.add_argument("source", help="Path to a chunks JSON file.")
    embed_cmd.add_argument("--output")
    embed_cmd.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)

    retrieve_cmd = sub.add_parser("retrieve")
    retrieve_cmd.add_argument("query")
    retrieve_cmd.add_argument(
        "--embeddings",
        default=path_for(EMBEDDINGS, DEFAULT_PDF, ".npy"),
        help="Path to an embeddings .npy file.",
    )
    retrieve_cmd.add_argument("--top-k", type=int, default=5)
    retrieve_cmd.add_argument("--model", default=None)

    generate_cmd = sub.add_parser("generate")
    generate_cmd.add_argument("query")
    generate_cmd.add_argument("--mode", default="cheatsheet")
    generate_cmd.add_argument("--top-k", type=int, default=5)
    generate_cmd.add_argument("--min-score", type=float, default=0.5)
    generate_cmd.add_argument(
        "--embeddings",
        default=path_for(EMBEDDINGS, DEFAULT_PDF, ".npy"),
        help="Path to an embeddings .npy file.",
    )
    generate_cmd.add_argument("--embedding-model", default=None)
    generate_cmd.add_argument(
        "--provider",
        choices=("ollama", "openai"),
        default=os.environ.get("RAG_LLM_PROVIDER", "ollama"),
    )
    generate_cmd.add_argument("--llm-model", default=os.environ.get("RAG_LLM_MODEL"))
    generate_cmd.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL))
    generate_cmd.add_argument("--output", default=None)

    return parser.parse_args()

def main() -> None:
    args = parse_args()
    ensure_output_dirs()

    if args.command == "extract":
        run_extract(args.pdf, args.output)
    elif args.command == "clean":
        run_clean(args.source, args.output)
    elif args.command == "structure":
        run_structure(args.source, args.output)
    elif args.command == "chunk":
        run_chunk(args.source, args.output, args.markdown_output)
    elif args.command == "embed":
        embed_chunks(args.source, args.output, args.model)
    elif args.command == "retrieve":
        print_results(retrieve_chunks(args.query, args.embeddings, args.top_k, args.model))
    elif args.command == "generate":
        generate_answer(
            args.query,
            args.embeddings,
            mode=args.mode,
            top_k=args.top_k,
            min_score=args.min_score,
            embedding_model=args.embedding_model,
            provider=args.provider,
            llm_model=args.llm_model,
            ollama_url=args.ollama_url,
            output=args.output,
        )
    else:
        run_all(getattr(args, "pdf", DEFAULT_PDF), args)

if __name__ == '__main__':
    main()
