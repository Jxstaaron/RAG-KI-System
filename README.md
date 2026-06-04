# RAG-KI-System

This project is now split into a reusable RAG backend plus a web app:

```text
backend/main.py       FastAPI API for upload, generate, and download
backend/pipeline/     PDF extraction, cleaning, chunking, embeddings, retrieval, generation
frontend/             Next.js + TailwindCSS user interface
rag_pipeline.py       CLI entry point for pipeline testing
```

## Run the Web App

Start Ollama first:

```bash
ollama run llama3.2
```

Start the FastAPI backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## User Flow

1. Drag and drop a PDF onto the upload area.
2. The backend saves it to `backend/data/pdfs/file.pdf`.
3. The pipeline extracts, cleans, structures, chunks, and embeds the PDF.
4. Select one mode: `Cheatsheet`, `Summary`, `Quiz`, `Flashcards`, or `Explanation`.
5. Click `Generate`.
6. The output appears in the center panel.
7. Click `Download PDF` to download the generated material.

## CLI Pipeline

```bash
python rag_pipeline.py run
```

Available stages:

```bash
python rag_pipeline.py extract backend/data/pdfs/file.pdf
python rag_pipeline.py clean backend/data/extracted_text/file.md
python rag_pipeline.py structure backend/data/cleaned_text/file.txt
python rag_pipeline.py chunk backend/data/structured_blocks/file.json
python rag_pipeline.py embed backend/data/chunks/file.json
```

The `embed` stage uses `paraphrase-multilingual-MiniLM-L12-v2` by default, which works well for German text and runs locally. It writes two files:

```text
backend/data/embeddings/file.npy
backend/data/embeddings/file_metadata.json
```

You can test retrieval from the terminal:

```bash
python rag_pipeline.py retrieve "Welche ökologischen Probleme entstehen beim Bananenanbau?"
```

Generate an answer with the retrieved chunks:

```bash
python rag_pipeline.py generate "Erstelle einen Spickzettel zu den ökologischen Problemen beim Bananenanbau" --mode cheatsheet --top-k 3
```

By default, generation uses a local Ollama model named `llama3.2`. If your model has a different name, pass it explicitly:

```bash
python rag_pipeline.py generate "Erstelle einen Spickzettel zu den ökologischen Problemen beim Bananenanbau" --mode cheatsheet --top-k 3 --llm-model llama3
```

Generation also uses `--min-score 0.5` by default. If the retrieved chunks are too unrelated to the question, the command stops instead of giving the model the wrong context.

You can still use OpenAI instead:

```bash
export OPENAI_API_KEY=your_api_key_here
python rag_pipeline.py generate "Erstelle einen Spickzettel zu den ökologischen Problemen beim Bananenanbau" --provider openai --llm-model gpt-4o-mini
```

Available generation modes:

```text
cheatsheet
summary
quiz
flashcards
explanation
```
    
