from __future__ import annotations

from pathlib import Path


def extract_pdf(pdf: str | Path) -> str:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    return PdfConverter(artifact_dict=create_model_dict())(str(pdf)).markdown
