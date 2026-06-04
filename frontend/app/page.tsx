"use client";

import { DragEvent, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const modes = [
  { id: "cheatsheet", label: "Cheatsheet" },
  { id: "summary", label: "Summary" },
  { id: "quiz", label: "Quiz" },
  { id: "flashcards", label: "Flashcards" },
  { id: "explanation", label: "Explanation" },
];

type Status = "idle" | "uploading" | "ready" | "generating" | "error";

async function parseApiError(response: Response, fallback: string) {
  const error = await response.json().catch(() => ({}));
  return error.detail ?? error.message ?? fallback;
}

function networkErrorMessage(error: unknown) {
  if (error instanceof TypeError) {
    return `Backend not reachable at ${API_URL}. Start FastAPI with: uvicorn backend.main:app --reload --port 8000`;
  }
  return error instanceof Error ? error.message : "Request failed.";
}

export default function Home() {
  const [selectedMode, setSelectedMode] = useState("cheatsheet");
  const [fileName, setFileName] = useState("");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("Drop a PDF to begin.");
  const [isDragging, setIsDragging] = useState(false);

  const canGenerate = useMemo(() => status === "ready" || Boolean(fileName), [fileName, status]);

  async function uploadFile(file: File) {
    if (file.type !== "application/pdf") {
      setStatus("error");
      setMessage("Please upload a PDF file.");
      return;
    }

    setStatus("uploading");
    setMessage("Processing PDF through the RAG pipeline...");
    setAnswer("");

    const data = new FormData();
    data.append("file", file);

    const response = await fetch(`${API_URL}/upload`, {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      throw new Error(await parseApiError(response, "Upload failed."));
    }

    setFileName(file.name);
    setStatus("ready");
    setMessage("PDF processed. Choose a mode and generate.");
  }

  async function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (!file) return;

    try {
      await uploadFile(file);
    } catch (error) {
      setStatus("error");
      setMessage(networkErrorMessage(error));
    }
  }

  async function handleGenerate() {
    setStatus("generating");
    setMessage("Generating with local Ollama...");

    try {
      const response = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: selectedMode,
          query: query.trim() || undefined,
          top_k: 5,
          min_score: 0.25,
          llm_model: "llama3.2:latest",
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? data.message ?? "Generation failed.");
      }

      setAnswer(data.answer);
      setStatus("ready");
      setMessage("Output ready.");
    } catch (error) {
      setStatus("error");
      setMessage(networkErrorMessage(error));
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-5 py-7">
      <header className="flex flex-col gap-3 rounded-lg border border-line bg-panel/90 px-6 py-5 shadow-2xl shadow-black/30 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violetSoft">
            AI Project RAG
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-normal text-white md:text-4xl">
            PDF Learning Assistant
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            Upload a PDF, choose a study mode, generate learning material, then download the result.
          </p>
        </div>
        <div className="rounded-md border border-line bg-panelSoft px-4 py-3 text-sm text-slate-200">
          <span className="mr-2 inline-block h-2 w-2 rounded-full bg-violet" />
          {message}
        </div>
      </header>

      <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <label
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={[
              "flex min-h-72 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition",
              isDragging
                ? "border-violet bg-violet/15"
                : "border-line bg-panel hover:border-violet/70 hover:bg-panelSoft",
            ].join(" ")}
          >
            <input
              type="file"
              accept="application/pdf"
              className="sr-only"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                try {
                  await uploadFile(file);
                } catch (error) {
                  setStatus("error");
                  setMessage(networkErrorMessage(error));
                }
              }}
            />
            <div className="mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-violet text-3xl font-black text-white">
              +
            </div>
            <h2 className="text-xl font-bold text-white">Drag PDF here</h2>
            <p className="mt-2 max-w-sm text-sm leading-6 text-slate-300">
              Or click to choose a file. The backend will extract, clean, chunk, and embed it.
            </p>
            {fileName && (
              <p className="mt-5 rounded-md bg-ink px-3 py-2 text-sm text-violetSoft">{fileName}</p>
            )}
          </label>

          <section className="rounded-lg border border-line bg-panel p-5">
            <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-slate-300">
              Mode
            </h2>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {modes.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={[
                    "rounded-md border px-4 py-3 text-sm font-bold transition",
                    selectedMode === mode.id
                      ? "border-violet bg-violet text-white"
                      : "border-line bg-panelSoft text-slate-200 hover:border-violet/80",
                  ].join(" ")}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </section>
        </div>

        <section className="flex min-h-[560px] flex-col rounded-lg border border-line bg-panel shadow-2xl shadow-black/20">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-lg font-bold text-white">Generated Output</h2>
            <p className="mt-1 text-sm text-slate-400">
              Optional: add a custom instruction before generating.
            </p>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Example: Erstelle einen Spickzettel zu den wichtigsten Folgen..."
              className="mt-4 min-h-24 w-full resize-y rounded-md border border-line bg-ink px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500"
            />
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={handleGenerate}
                disabled={!canGenerate || status === "uploading" || status === "generating"}
                className="rounded-md bg-violet px-5 py-3 text-sm font-bold text-white transition hover:bg-violetSoft disabled:cursor-not-allowed disabled:opacity-50"
              >
                {status === "generating" ? "Generating..." : "Generate"}
              </button>
              <a
                href={`${API_URL}/download`}
                className={[
                  "rounded-md border border-line px-5 py-3 text-sm font-bold text-slate-100 transition hover:border-violet",
                  answer ? "" : "pointer-events-none opacity-50",
                ].join(" ")}
              >
                Download PDF
              </a>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            <pre className="min-h-full whitespace-pre-wrap rounded-md bg-ink p-5 text-sm leading-7 text-slate-100">
              {answer || "Your generated result will appear here."}
            </pre>
          </div>
        </section>
      </section>
    </main>
  );
}
