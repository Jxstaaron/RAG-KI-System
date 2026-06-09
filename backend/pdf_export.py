from __future__ import annotations
"""PDF-Export für die zuletzt generierte Lernantwort."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from backend.pipeline.config import GENERATED


def export_answer_pdf(answer: str, filename: str = "output.pdf") -> Path:
    """Schreibt die generierte Antwort mit ReportLab in eine PDF-Datei."""

    GENERATED.mkdir(parents=True, exist_ok=True)
    output = GENERATED / filename

    styles = getSampleStyleSheet()
    title = styles["Title"]
    body = styles["BodyText"]
    body.leading = 14

    # ReportLab baut PDFs aus einzelnen Elementen wie Paragraph und Spacer.
    story = [Paragraph("Generated Learning Material", title), Spacer(1, 18)]
    for paragraph in answer.split("\n"):
        text = paragraph.strip() or "&nbsp;"
        story.append(Paragraph(text, body))
        story.append(Spacer(1, 6))

    document = SimpleDocTemplate(str(output), pagesize=A4)
    document.build(story)
    return output
