from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict


def extract_pdf(pdf_path: str) -> str:
    """
    Extract markdown text from PDF using Marker.
    Handles:
    - OCR
    - layout reconstruction
    - headings
    - lists
    """

    converter = PdfConverter(
        artifact_dict=create_model_dict()
    )

    result = converter(pdf_path)

    return result.markdown

