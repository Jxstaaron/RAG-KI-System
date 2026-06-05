# RAG-KI-System

Dieses Projekt ist ein Lernassistent für PDF-Dateien. Man lädt eine PDF hoch und
das System kann daraus zum Beispiel einen Spickzettel, eine Zusammenfassung, ein
Quiz oder Karteikarten erstellen. Außerdem gibt es einen eigenen Frage-Modus, in
dem man mit dem System über die PDF chatten kann.

## Was Bedeutet RAG?

RAG steht für `Retrieval Augmented Generation`.

Ein normales Sprachmodell antwortet nur mit seinem allgemeinen Wissen. Unser
System macht vorher noch einen extra Schritt:

```text
PDF
-> Text extrahieren
-> Text bereinigen
-> Text in Abschnitte aufteilen
-> Embeddings berechnen
-> passende Abschnitte suchen
-> Antwort mit LLM erzeugen
```

Das Sprachmodell bekommt also nicht einfach nur die Frage, sondern auch die
passenden Textstellen aus der PDF. Dadurch soll die Antwort besser zur
hochgeladenen Datei passen.

## Projektstruktur

```text
backend/main.py       FastAPI-Backend für Upload, Generierung und Download
backend/pipeline/     Eigentliche RAG-Pipeline
frontend/             Webseite mit Next.js und TailwindCSS
rag_pipeline.py       Startdatei für Tests über das Terminal
```

## Web-App Starten

Zuerst muss Ollama mit dem lokalen Modell laufen:

```bash
ollama run llama3.2
```

Dann startet man das Backend im Projektordner:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

In einem zweiten Terminal startet man das Frontend:

```bash
cd frontend
npm install
npm run dev -- --hostname 0.0.0.0
```

Auf dem gleichen Rechner öffnet man:

```text
http://localhost:3000
```

Auf einem anderen Gerät im gleichen Netzwerk benutzt man die Netzwerk-Adresse,
die Next.js im Terminal anzeigt, zum Beispiel:

```text
Frontend: http://192.168.178.33:3000
Backend:  http://192.168.178.33:8000
```

Zum Testen, ob das Backend erreichbar ist, kann man im Browser öffnen:

```text
http://192.168.178.33:8000/health
```

Wenn alles funktioniert, kommt zurück:

```json
{"ok":true}
```

## Bedienung Der Webseite

1. Eine PDF unten in die Upload-Leiste ziehen oder anklicken.
2. Warten, bis die Pipeline fertig ist.
3. Rechts einen Modus auswählen.
4. Auf `Generieren` klicken.
5. Die Antwort erscheint in der Mitte als Chat-Nachricht.
6. Mit `PDF herunterladen` kann die Antwort als PDF gespeichert werden.

Es gibt diese Modi:

```text
Spickzettel
Zusammenfassung
Quiz
Karteikarten
Eigene Frage
```

Bei `Eigene Frage` kann man selbst Fragen zur PDF stellen. Die Antworten werden
als Chat angezeigt. Links werden bis zu 10 Chat-Verläufe gespeichert.

## Pipeline Über Das Terminal Testen

Die komplette Pipeline kann man so starten:

```bash
python rag_pipeline.py run
```

Einzelne Schritte kann man auch getrennt testen:

```bash
python rag_pipeline.py extract backend/data/pdfs/file.pdf
python rag_pipeline.py clean backend/data/extracted_text/file.md
python rag_pipeline.py structure backend/data/cleaned_text/file.txt
python rag_pipeline.py chunk backend/data/structured_blocks/file.json
python rag_pipeline.py embed backend/data/chunks/file.json
```

Die Embeddings werden standardmäßig mit diesem Modell erstellt:

```text
paraphrase-multilingual-MiniLM-L12-v2
```

Das Modell funktioniert gut für deutsche Texte und läuft lokal auf dem Rechner.
Die Embeddings werden hier gespeichert:

```text
backend/data/embeddings/file.npy
backend/data/embeddings/file_metadata.json
```

## Retrieval Testen

Mit Retrieval sucht das System die passendsten Chunks zu einer Frage:

```bash
python rag_pipeline.py retrieve "Welche ökologischen Probleme entstehen beim Bananenanbau?"
```

Eine Antwort kann man auch direkt über das Terminal erzeugen:

```bash
python rag_pipeline.py generate "Erstelle einen Spickzettel zu den ökologischen Problemen beim Bananenanbau" --mode cheatsheet --top-k 3
```

Standardmäßig wird lokal Ollama mit `llama3.2` benutzt. Wenn das Modell anders
heißt, kann man den Namen angeben:

```bash
python rag_pipeline.py generate "Erstelle einen Spickzettel" --mode cheatsheet --llm-model llama3
```

## Wichtige Hinweise

- Das Projekt braucht Python-Abhängigkeiten aus `requirements.txt`.
- Das Frontend braucht Node.js und die Pakete aus `frontend/package.json`.
- Ollama muss laufen, damit lokal Antworten generiert werden können.
- Die Chat-Verläufe werden nur im Browser gespeichert, nicht in einer Datenbank.
- Generierte Dateien wie Chunks, Embeddings und PDFs liegen im Ordner `backend/data`.
