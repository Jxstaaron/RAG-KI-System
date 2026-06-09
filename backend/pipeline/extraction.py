from __future__ import annotations
"""PDF-Extraktion mit Marker.

Marker erkennt Layout, Text und Tabellen und gibt das Ergebnis als Markdown
zurück. Diese Stufe ist meistens die langsamste, weil OCR nötig sein kann.
"""

from pathlib import Path


def extract_pdf(pdf: str | Path) -> str:
    """Extrahiert eine PDF-Datei als Markdown-Text."""

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    return PdfConverter(artifact_dict=create_model_dict())(str(pdf)).markdown
