from __future__ import annotations
"""Kleiner Einstiegspunkt für die RAG-Pipeline-CLI.

Die eigentliche Logik liegt in backend.pipeline.cli. Diese Datei bleibt im
Projektwurzelordner, damit Befehle wie `python rag_pipeline.py run` kurz sind.
"""

from backend.pipeline.cli import main


if __name__ == "__main__":
    # Nur ausführen, wenn die Datei direkt per Python gestartet wird.
    main()
