import re
import unicodedata

from backend.ingestion.structure import is_heading, is_list_item


def normalize_unicode(text: str) -> str:
    """
    Normalize unicode for consistent embeddings.
    """

    return unicodedata.normalize("NFKC", text)


def decode_unicode_escapes(text: str) -> str:
    """
    Convert:
    \\u00e4 -> ä
    """

    if not re.search(r'\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}', text):
        return text

    try:
        return text.encode().decode("unicode_escape")
    except Exception:
        return text


def repair_mojibake(text: str) -> str:
    """
    Repair common UTF-8 text that was decoded as Latin-1/Windows-1252.
    Example:
    Ã¼ -> ü
    Â° -> °
    """

    try:
        from ftfy import fix_text

        return fix_text(text)
    except Exception:
        replacements = {
            "Ã¤": "ä",
            "Ã¶": "ö",
            "Ã¼": "ü",
            "Ã„": "Ä",
            "Ã–": "Ö",
            "Ãœ": "Ü",
            "ÃŸ": "ß",
            "Â°": "°",
            "Â": "",
        }

        for bad, good in replacements.items():
            text = text.replace(bad, good)

        return text


def remove_image_placeholders(text: str) -> str:
    """
    Remove markdown image references.
    """

    return re.sub(r'!\[\]\(.*?\)', '', text)


def fix_hyphenation(text: str) -> str:
    """
    Fix:
    Bei-
    spiel

    -> Beispiel
    """

    return re.sub(r'(\w)-\n(\w)', r'\1\2', text)


def fix_spaced_umlauts(text: str) -> str:
    """
    Fix OCR spacing artifacts:
    pr üfen -> prüfen
    f ür -> für
    """

    patterns = [
        (r'\b([A-Za-z]{1,2})\s+ä', r'\1ä'),
        (r'\b([A-Za-z]{1,2})\s+ö', r'\1ö'),
        (r'\b([A-Za-z]{1,2})\s+ü', r'\1ü'),
        (r'\b([A-Za-z]{1,2})\s+Ä', r'\1Ä'),
        (r'\b([A-Za-z]{1,2})\s+Ö', r'\1Ö'),
        (r'\b([A-Za-z]{1,2})\s+Ü', r'\1Ü'),
    ]

    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text)

    return text


def normalize_temperature_units(text: str) -> str:
    """
    Normalize:
    20 °C -> 20°C
    """

    return re.sub(r'(\d+)\s*°\s*C', r'\1°C', text)


def remove_page_artifacts(text: str) -> str:
    """
    Remove common page artifacts.
    """

    patterns = [
        r'Seite\s+\d+',
        r'Page\s+\d+',
    ]

    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    return text


def remove_material_refs(text: str) -> str:
    """
    Remove textbook references:
    M1
    M2*
    M7
    """

    return re.sub(r'\bM\d+\*?\b', '', text)


def is_noise_line(line: str) -> bool:
    """
    Detect low-information OCR noise.
    """

    stripped = line.strip()

    if not stripped:
        return False

    # isolated numbers
    if re.fullmatch(r'[\d\s.,%$€-]+', stripped):
        return True

    # random publisher/export junk
    if re.search(r'©|WTO|EX', stripped):
        return True

    # weird IDs
    if re.fullmatch(r'[A-Z0-9]{6,}', stripped):
        return True

    return False


def remove_noise_lines(text: str) -> str:
    """
    Remove noisy OCR/table artifacts.
    """

    cleaned = []

    for line in text.splitlines():

        if is_noise_line(line):
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


def merge_wrapped_lines(text: str) -> str:
    """
    Merge wrapped lines while preserving:
    - headings
    - lists
    - paragraphs
    """

    lines = text.splitlines()

    merged = []

    for line in lines:

        stripped = line.strip()

        # preserve empty lines
        if not stripped:
            merged.append("")
            continue

        # preserve headings
        if is_heading(stripped):
            merged.append(stripped)
            continue

        # preserve new list items
        if is_list_item(stripped):
            merged.append(stripped)
            continue

        # preserve image placeholders
        if stripped.startswith("!["):
            merged.append(stripped)
            continue

        # merge normal paragraph lines and wrapped list continuations
        if merged:

            prev = merged[-1]

            if (
                prev != ""
                and not is_heading(prev)
            ):
                merged[-1] = prev + " " + stripped
            else:
                merged.append(stripped)

        else:
            merged.append(stripped)

    return "\n".join(merged)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace/newlines.
    """

    # trailing spaces
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # multiple spaces
    text = re.sub(r'[ ]{2,}', ' ', text)

    # excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def clean_text(text: str) -> str:

    text = decode_unicode_escapes(text)

    text = repair_mojibake(text)

    text = normalize_unicode(text)

    text = remove_image_placeholders(text)

    text = fix_hyphenation(text)

    text = normalize_temperature_units(text)

    text = remove_page_artifacts(text)

    text = remove_material_refs(text)

    text = remove_noise_lines(text)

    text = merge_wrapped_lines(text)

    text = fix_spaced_umlauts(text)

    text = normalize_whitespace(text)

    return text
