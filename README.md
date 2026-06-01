# RAG-KI-System

The command line entry point is:

```bash
python rag_pipeline.py run
```

The implementation is split by responsibility under `backend/pipeline/`:

```text
config.py           paths and default models
io.py               text/json file helpers
extraction.py       PDF extraction
text_processing.py  cleaning and structuring
chunking.py         chunk creation and markdown preview
embeddings.py       embedding model loading and vector export
retrieval.py        vector similarity search
generation.py       prompt building and LLM/Ollama calls
stages.py           pipeline stage wrappers
cli.py              command line interface
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
    
