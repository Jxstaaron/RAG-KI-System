"use client";

import { DragEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const modes = [
  { id: "cheatsheet", label: "Cheatsheet" },
  { id: "summary", label: "Zusammenfassung" },
  { id: "quiz", label: "Quiz" },
  { id: "flashcards", label: "Karteikarten" },
  { id: "explanation", label: "Erklärung" },
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
  const [visibleAnswer, setVisibleAnswer] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("Drop a PDF to begin.");
  const [isDragging, setIsDragging] = useState(false);

  const canGenerate = useMemo(() => status === "ready" || Boolean(fileName), [fileName, status]);

  useEffect(() => {
    setVisibleAnswer("");
    if (!answer) return;

    let index = 0;
    const timer = window.setInterval(() => {
      index += 4;
      setVisibleAnswer(answer.slice(0, index));
      if (index >= answer.length) {
        window.clearInterval(timer);
      }
    }, 18);

    return () => window.clearInterval(timer);
  }, [answer]);

  async function uploadFile(file: File) {
    if (file.type !== "application/pdf") {
      setStatus("error");
      setMessage("Please upload a PDF file.");
      return;
    }

    setStatus("uploading");
    setMessage("Processing PDF through the RAG pipeline...");
    setAnswer("");
    setVisibleAnswer("");

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
    setAnswer("");
    setVisibleAnswer("");

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
    <main className="grid min-h-screen grid-rows-[auto_1fr] bg-ink text-slate-100">
      <header className="border-b border-line bg-panel px-5 py-4 shadow-xl shadow-black/20">
        <div className="flex w-full flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-violetSoft">
              KI Projekt RAG
            </p>
            <h1 className="mt-1 text-2xl font-bold tracking-normal text-white md:text-3xl">
              KI-gestützer Lernassistent
            </h1>
          </div>
          <div className="max-w-xl rounded-md border border-line bg-panelSoft px-4 py-3 text-sm text-slate-200">
            <span className="mr-2 inline-block h-2 w-2 rounded-full bg-violet" />
            {message}
          </div>
        </div>
      </header>

      <section className="grid min-h-0 w-full grid-cols-1 gap-0 border-t border-line lg:grid-cols-[280px_1fr_320px]">
        <aside className="flex min-h-[280px] flex-col border-b border-line bg-panel lg:border-b-0 lg:border-r">
          <div className="border-b border-line px-4 py-4">
            <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-slate-300">
              Chats
            </h2>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {["Current PDF", "Example session", "Saved summary"].map((item, index) => (
              <button
                key={item}
                disabled
                className={[
                  "w-full rounded-md border px-3 py-3 text-left text-sm transition",
                  index === 0
                    ? "border-violet/60 bg-violet/15 text-white"
                    : "border-line bg-panelSoft text-slate-400",
                ].join(" ")}
              >
                {item}
                <span className="mt-1 block text-xs text-slate-500">Placeholder</span>
              </button>
            ))}
          </div>

        </aside>

        <section className="flex min-h-[640px] flex-col bg-panel">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-lg font-bold text-white">Chat</h2>
            <p className="mt-1 text-sm text-slate-400">
              Ask a question or leave this empty to generate from the selected mode.
            </p>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col gap-4 px-4 py-4">
              <div className="min-h-0 flex-1 overflow-y-auto">
                {query.trim() && (
                  <div className="mb-4 max-w-2xl self-start rounded-lg bg-violet px-4 py-3 text-sm leading-6 text-white">
                    {query}
                  </div>
                )}

              <div className="min-h-full bg-panel px-2 py-3 text-sm leading-7 text-slate-100">
                {visibleAnswer ? (
                  <ReactMarkdown
                    components={{
                      h1: ({ children }) => (
                        <h1 className="mb-3 mt-5 text-2xl font-bold text-white">{children}</h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="mb-2 mt-4 text-xl font-bold text-white">{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="mb-2 mt-3 text-lg font-bold text-white">{children}</h3>
                      ),
                      p: ({ children }) => <p className="mb-3 text-slate-100">{children}</p>,
                      strong: ({ children }) => (
                        <strong className="font-bold text-white">{children}</strong>
                      ),
                      ul: ({ children }) => (
                        <ul className="mb-4 list-disc space-y-1 pl-6">{children}</ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="mb-4 list-decimal space-y-1 pl-6">{children}</ol>
                      ),
                      li: ({ children }) => <li className="pl-1">{children}</li>,
                    }}
                  >
                    {visibleAnswer}
                  </ReactMarkdown>
                ) : (
                  <p className="text-slate-400">
                    Generated output will appear here as the assistant response.
                  </p>
                )}
              </div>
              </div>

              <div className="grid gap-3 lg:grid-cols-[minmax(0,01fr)_150px]">
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Ask about the PDF, or leave empty for the selected mode..."
                  className="min-h-24 w-full resize-none rounded-md border border-line bg-panel px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500"
                />

                <div className="flex flex-col gap-3 self-start">
                  <button
                    onClick={handleGenerate}
                    disabled={!canGenerate || status === "uploading" || status === "generating"}
                    className="rounded-md bg-violet px-4 py-3 text-sm font-bold text-white transition hover:bg-violetSoft disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {status === "generating" ? "Generating..." : "Generate"}
                  </button>
                  <a
                    href={`${API_URL}/download`}
                    className={[
                      "rounded-md border border-line px-4 py-3 text-center text-sm font-bold text-slate-100 transition hover:border-violet",
                      answer ? "" : "pointer-events-none opacity-50",
                    ].join(" ")}
                  >
                    Download PDF
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside className="flex flex-col border-t border-line bg-panel p-4 lg:border-l lg:border-t-0">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-slate-300">
              Mode
            </h2>
            <div className="mt-4 grid gap-3">
              {modes.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={[
                    "rounded-md border px-4 py-3 text-left text-sm font-bold transition",
                    selectedMode === mode.id
                      ? "border-violet bg-violet text-white"
                      : "border-line bg-panelSoft text-slate-200 hover:border-violet/80",
                  ].join(" ")}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>

          <label
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={[
              "mt-6 flex min-h-44 cursor-pointer flex-col justify-center rounded-lg border-2 border-dashed p-4 transition lg:mt-auto",
              isDragging
                ? "border-violet bg-violet/15"
                : "border-line bg-panelSoft hover:border-violet/70",
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
            <div className="mb-3 grid h-10 w-10 place-items-center rounded-md bg-violet text-xl font-black text-white">
              +
            </div>
            <h2 className="text-base font-bold text-white">Drag PDF here</h2>
            <p className="mt-1 text-sm leading-5 text-slate-400">Or click to upload.</p>
            {fileName && (
              <p className="mt-3 truncate rounded-md bg-ink px-3 py-2 text-xs text-violetSoft">
                {fileName}
              </p>
            )}
          </label>

          <button
            onClick={handleGenerate}
            disabled={!canGenerate || status === "uploading" || status === "generating"}
            className="mt-3 rounded-md bg-violet px-4 py-3 text-sm font-bold text-white transition hover:bg-violetSoft disabled:cursor-not-allowed disabled:opacity-50"
          >
            {status === "generating" ? "Generating..." : "Generate"}
          </button>
        </aside>
      </section>
    </main>
  );
}
