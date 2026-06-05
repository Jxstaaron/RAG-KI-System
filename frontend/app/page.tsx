"use client";

import { DragEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const CONFIGURED_API_URL = process.env.NEXT_PUBLIC_API_URL;

// Wenn keine API-URL gesetzt ist, wird automatisch derselbe Host wie im Browser
// verwendet. Dadurch funktioniert die App lokal und auch im Netzwerk.
function getBrowserApiUrl() {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }

  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

const modes = [
  { id: "cheatsheet", label: "Spickzettel" },
  { id: "summary", label: "Zusammenfassung" },
  { id: "quiz", label: "Quiz" },
  { id: "flashcards", label: "Karteikarten" },
  { id: "custom", label: "Eigene Frage" },
];

const CHAT_HISTORY_KEY = "rag-learning-assistant-chats";
const MAX_CHATS = 10;

type Status = "idle" | "uploading" | "ready" | "generating" | "error";

type PipelineProgress = {
  status: string;
  stage: string;
  label: string;
  progress: number;
};

type ChatMessage = {
  // "thinking" ist eine temporäre Nachricht, solange das LLM noch antwortet.
  id: string;
  role: "user" | "assistant" | "thinking";
  content: string;
  mode?: string;
  createdAt: number;
};

type ChatSession = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
};

async function parseApiError(response: Response, fallback: string) {
  // FastAPI liefert Fehler meistens als JSON mit detail/message zurück.
  const error = await response.json().catch(() => ({}));
  return error.detail ?? error.message ?? fallback;
}

function networkErrorMessage(error: unknown, apiUrl: string) {
  if (error instanceof TypeError) {
    return `Backend nicht erreichbar unter ${apiUrl}. Starte FastAPI mit: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`;
  }
  return error instanceof Error ? error.message : "Anfrage fehlgeschlagen.";
}

function isPdfFile(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function createId(prefix: string) {
  // Einfache eindeutige ID für Chats und Nachrichten im Frontend.
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createChatSession(title = "Neuer Chat"): ChatSession {
  const now = Date.now();
  return {
    id: createId("chat"),
    title,
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

function modeLabel(modeId: string) {
  return modes.find((mode) => mode.id === modeId)?.label ?? modeId;
}

function truncateTitle(text: string) {
  const clean = text.trim().replace(/\s+/g, " ");
  return clean.length > 34 ? `${clean.slice(0, 31)}...` : clean || "Neuer Chat";
}

function thinkingText(step: number) {
  // Erzeugt die animierten Punkte: ".", "..", "...".
  return `Llama denkt nach${".".repeat((step % 3) + 1)}`;
}

export default function Home() {
  const [selectedMode, setSelectedMode] = useState("cheatsheet");
  const [fileName, setFileName] = useState("");
  const [query, setQuery] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>(() => [createChatSession()]);
  const [activeChatId, setActiveChatId] = useState(() => sessions[0].id);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("PDF ablegen, um zu starten.");
  const [isDragging, setIsDragging] = useState(false);
  const [apiUrl, setApiUrl] = useState(CONFIGURED_API_URL ?? "http://127.0.0.1:8000");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStageLabel, setUploadStageLabel] = useState("Bereit");
  // fileInputRef erlaubt es, den unsichtbaren Datei-Input über die Upload-Leiste zu öffnen.
  const fileInputRef = useRef<HTMLInputElement>(null);
  // outputScrollRef wird genutzt, um den Chat automatisch nach unten zu scrollen.
  const outputScrollRef = useRef<HTMLDivElement>(null);
  // Verhindert, dass der leere Startzustand direkt den gespeicherten Verlauf überschreibt.
  const hasLoadedChatsRef = useRef(false);

  const canGenerate = useMemo(() => status === "ready" || Boolean(fileName), [fileName, status]);
  const isCustomMode = selectedMode === "custom";
  const activeChat = useMemo(
    () => sessions.find((session) => session.id === activeChatId) ?? sessions[0],
    [activeChatId, sessions],
  );
  const hasGeneratedAnswer = useMemo(
    () => Boolean(activeChat?.messages.some((chatMessage) => chatMessage.role === "assistant")),
    [activeChat],
  );

  useEffect(() => {
    // API-URL nach dem ersten Render im Browser bestimmen.
    if (!CONFIGURED_API_URL) {
      setApiUrl(getBrowserApiUrl());
    }
  }, []);

  useEffect(() => {
    // Chat-Verläufe aus localStorage laden. Das ist einfach und braucht keine Datenbank.
    const stored = window.localStorage.getItem(CHAT_HISTORY_KEY);
    if (!stored) {
      hasLoadedChatsRef.current = true;
      return;
    }

    try {
      const parsed = JSON.parse(stored) as ChatSession[];
      if (!Array.isArray(parsed) || parsed.length === 0) {
        hasLoadedChatsRef.current = true;
        return;
      }
      const validSessions = parsed
        .filter((session) => session.id && Array.isArray(session.messages))
        .slice(0, MAX_CHATS);
      if (validSessions.length === 0) {
        hasLoadedChatsRef.current = true;
        return;
      }
      setSessions(validSessions);
      setActiveChatId(validSessions[0].id);
    } catch {
      window.localStorage.removeItem(CHAT_HISTORY_KEY);
    } finally {
      hasLoadedChatsRef.current = true;
    }
  }, []);

  useEffect(() => {
    // Jede Änderung an den Chats wird lokal im Browser gespeichert.
    if (!hasLoadedChatsRef.current) return;
    window.localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(sessions.slice(0, MAX_CHATS)));
  }, [sessions]);

  useEffect(() => {
    // Während die PDF verarbeitet wird, fragt das Frontend regelmäßig den echten
    // Pipeline-Status vom Backend ab.
    if (status !== "uploading") return;

    let isActive = true;

    async function loadProgress() {
      try {
        const response = await fetch(`${apiUrl}/progress`);
        if (!response.ok) return;
        const progress = (await response.json()) as PipelineProgress;
        if (!isActive) return;

        setUploadProgress(progress.progress);
        setUploadStageLabel(progress.label);
        setMessage(`Pipeline: ${progress.label}`);
      } catch {
        // Der Upload-Request selbst meldet Verbindungsfehler; Polling ist nur eine Statushilfe.
      }
    }

    void loadProgress();
    const timer = window.setInterval(loadProgress, 750);

    return () => {
      isActive = false;
      window.clearInterval(timer);
    };
  }, [apiUrl, status]);

  useEffect(() => {
    // Wenn eine neue Nachricht erscheint oder die Antwort weitergeschrieben wird,
    // bleibt der Chat automatisch am unteren Ende.
    if (!activeChat?.messages.length) return;

    const frame = window.requestAnimationFrame(() => {
      const output = outputScrollRef.current;
      if (!output) return;

      output.scrollTo({
        top: output.scrollHeight,
        behavior: "smooth",
      });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [activeChat?.messages]);

  function updateChat(chatId: string, updater: (session: ChatSession) => ChatSession) {
    // Hilfsfunktion, um genau einen Chat-Verlauf zu verändern.
    setSessions((currentSessions) =>
      currentSessions.map((session) =>
        session.id === chatId ? updater(session) : session,
      ),
    );
  }

  function updateActiveChat(updater: (session: ChatSession) => ChatSession) {
    updateChat(activeChatId, updater);
  }

  function appendMessage(chatMessage: ChatMessage, chatId = activeChatId) {
    // Fügt eine Nachricht an und benennt neue Chats automatisch nach der ersten Nachricht.
    updateChat(chatId, (session) => {
      const shouldRename = session.messages.length === 0;
      return {
        ...session,
        title: shouldRename
          ? truncateTitle(chatMessage.role === "user" ? chatMessage.content : modeLabel(chatMessage.mode ?? "custom"))
          : session.title,
        updatedAt: Date.now(),
        messages: [...session.messages, chatMessage],
      };
    });
  }

  function updateMessage(messageId: string, content: string, chatId = activeChatId) {
    // Wird für den Typewriter-Effekt und die "Llama denkt nach"-Animation genutzt.
    updateChat(chatId, (session) => ({
      ...session,
      updatedAt: Date.now(),
      messages: session.messages.map((chatMessage) =>
        chatMessage.id === messageId ? { ...chatMessage, content } : chatMessage,
      ),
    }));
  }

  function removeMessage(messageId: string, chatId = activeChatId) {
    updateChat(chatId, (session) => ({
      ...session,
      updatedAt: Date.now(),
      messages: session.messages.filter((chatMessage) => chatMessage.id !== messageId),
    }));
  }

  function startNewChat(title = "Neuer Chat") {
    // Es werden maximal 10 Chats behalten, damit die linke Liste übersichtlich bleibt.
    const session = createChatSession(title);
    setSessions((currentSessions) => [session, ...currentSessions].slice(0, MAX_CHATS));
    setActiveChatId(session.id);
    setQuery("");
  }

  function deleteChat(chatId: string) {
    // Der letzte Chat darf nicht komplett verschwinden; dann wird ein leerer neuer Chat angelegt.
    setSessions((currentSessions) => {
      const remaining = currentSessions.filter((session) => session.id !== chatId);
      if (remaining.length === 0) {
        const freshSession = createChatSession();
        setActiveChatId(freshSession.id);
        return [freshSession];
      }
      if (chatId === activeChatId) {
        setActiveChatId(remaining[0].id);
      }
      return remaining;
    });
  }

  function appendAssistantWithTypewriter(answerText: string, mode: string, chatId = activeChatId) {
    // Die Antwort wird nicht sofort komplett angezeigt, sondern Stück für Stück geschrieben.
    const assistantMessage: ChatMessage = {
      id: createId("assistant"),
      role: "assistant",
      content: "",
      mode,
      createdAt: Date.now(),
    };

    appendMessage(assistantMessage, chatId);

    let index = 0;
    const timer = window.setInterval(() => {
      index += 4;
      updateMessage(assistantMessage.id, answerText.slice(0, index), chatId);
      if (index >= answerText.length) {
        window.clearInterval(timer);
      }
    }, 18);
  }

  async function uploadFile(file: File) {
    // Upload startet die komplette Backend-Pipeline: Extraktion, Cleaning, Chunking, Embeddings.
    if (!isPdfFile(file)) {
      setStatus("error");
      setMessage("Bitte lade eine PDF-Datei hoch.");
      setUploadProgress(0);
      setUploadStageLabel("Bereit");
      return;
    }

    setStatus("uploading");
    setMessage("PDF wird durch die RAG-Pipeline verarbeitet...");
    setUploadProgress(5);
    setUploadStageLabel("PDF hochladen");

    const data = new FormData();
    data.append("file", file);

    const response = await fetch(`${apiUrl}/upload`, {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      throw new Error(await parseApiError(response, "Upload fehlgeschlagen."));
    }

    setFileName(file.name);
    setUploadProgress(100);
    setUploadStageLabel("Fertig");
    setStatus("ready");
    setMessage("PDF verarbeitet. Wähle einen Modus und generiere eine Antwort.");
    if ((activeChat?.messages.length ?? 0) > 0) {
      startNewChat(file.name);
    }
  }

  function handleDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
    setIsDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setIsDragging(false);
    }
  }

  async function handleDrop(event: DragEvent<HTMLElement>) {
    // Drag-and-drop liest die erste abgelegte Datei und behandelt sie wie einen normalen Upload.
    setIsDragging(false);
    event.preventDefault();
    event.stopPropagation();
    const file = event.dataTransfer.files?.[0];
    if (!file) return;

    try {
      await uploadFile(file);
    } catch (error) {
      setStatus("error");
      setUploadProgress(0);
      setUploadStageLabel("Fehler");
      setMessage(networkErrorMessage(error, apiUrl));
    }
  }

  async function handleGenerate() {
    // Feste Modi nutzen eine Standard-Aufgabe. Der Modus "Eigene Frage" nutzt den User-Text.
    if (isCustomMode && !query.trim()) {
      setStatus("error");
      setMessage("Bitte gib eine Frage für den Modus Eigene Frage ein.");
      return;
    }

    setStatus("generating");
    setMessage("Lokales Ollama generiert eine Antwort...");
    const trimmedQuery = query.trim();
    const activeMode = selectedMode;
    const targetChatId = activeChatId;

    if (isCustomMode) {
      appendMessage({
        id: createId("user"),
        role: "user",
        content: trimmedQuery,
        mode: activeMode,
        createdAt: Date.now(),
      }, targetChatId);
      setQuery("");
    }

    const thinkingMessageId = createId("thinking");
    // Solange das Backend rechnet, sieht der User eine temporäre Denk-Nachricht.
    appendMessage({
      id: thinkingMessageId,
      role: "thinking",
      content: thinkingText(0),
      mode: activeMode,
      createdAt: Date.now(),
    }, targetChatId);

    let thinkingStep = 0;
    const thinkingTimer = window.setInterval(() => {
      thinkingStep += 1;
      updateMessage(thinkingMessageId, thinkingText(thinkingStep), targetChatId);
    }, 450);

    try {
      const response = await fetch(`${apiUrl}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: activeMode,
          query: isCustomMode ? trimmedQuery : undefined,
          top_k: 5,
          min_score: 0.25,
          llm_model: "llama3.2:latest",
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? data.message ?? "Generierung fehlgeschlagen.");
      }

      window.clearInterval(thinkingTimer);
      removeMessage(thinkingMessageId, targetChatId);
      appendAssistantWithTypewriter(data.answer, activeMode, targetChatId);
      setStatus("ready");
      setMessage("Antwort ist fertig.");
    } catch (error) {
      window.clearInterval(thinkingTimer);
      removeMessage(thinkingMessageId, targetChatId);
      setStatus("error");
      setMessage(networkErrorMessage(error, apiUrl));
    }
  }

  async function handleFileSelect(file?: File) {
    if (!file) return;

    try {
      await uploadFile(file);
    } catch (error) {
      setStatus("error");
      setUploadProgress(0);
      setUploadStageLabel("Fehler");
      setMessage(networkErrorMessage(error, apiUrl));
    }
  }

  return (
    <main className="grid h-screen grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-ink text-slate-100">
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

      <section
        onDragEnter={handleDragOver}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="grid min-h-0 w-full grid-rows-[minmax(0,1fr)_auto] overflow-hidden border-t border-line"
      >
        <div className="grid min-h-0 w-full grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[280px_minmax(0,1fr)_320px]">
          <aside className="flex min-h-0 flex-col overflow-hidden border-b border-line bg-panel lg:border-b-0 lg:border-r">
            <div className="border-b border-line px-4 py-4">
              <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-slate-300">
                Verläufe
              </h2>
              <button
                type="button"
                onClick={() => startNewChat()}
                className="mt-3 w-full rounded-md border border-line bg-panelSoft px-3 py-2 text-left text-sm font-bold text-slate-100 transition hover:border-violet"
              >
                Neuer Chat
              </button>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto p-3">
              {[...sessions].sort((a, b) => b.updatedAt - a.updatedAt).map((session) => (
                <div
                  key={session.id}
                  className={[
                    "group grid grid-cols-[1fr_auto] items-start gap-2 rounded-md border p-2 transition",
                    session.id === activeChatId
                      ? "border-violet/60 bg-violet/15"
                      : "border-line bg-panelSoft",
                  ].join(" ")}
                >
                  <button
                    type="button"
                    onClick={() => setActiveChatId(session.id)}
                    className="min-w-0 text-left"
                  >
                    <span className="block truncate text-sm font-bold text-white">
                      {session.title}
                    </span>
                    <span className="mt-1 block text-xs text-slate-500">
                      {session.messages.length} Nachrichten
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteChat(session.id)}
                    className="rounded px-2 py-1 text-xs font-bold text-slate-400 transition hover:bg-ink hover:text-white"
                    aria-label={`${session.title} löschen`}
                  >
                    x
                  </button>
                </div>
              ))}
            </div>

          </aside>

          <section className="flex min-h-0 flex-col overflow-hidden bg-panel">
            <div className="border-b border-line px-5 py-4">
              <h2 className="text-lg font-bold text-white">Ausgabe</h2>
              <p className="mt-1 text-sm text-slate-400">
                Lade eine PDF hoch, wähle einen Modus und generiere dein Lernmaterial.
              </p>
            </div>

            <div ref={outputScrollRef} className="min-h-0 flex-1 overflow-y-auto">
              <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col gap-4 px-4 py-4">
                <div className="flex min-h-0 flex-1 flex-col gap-3">
                  {activeChat?.messages.length ? (
                    activeChat.messages.map((chatMessage) => (
                      <div
                        key={chatMessage.id}
                        className={[
                          "flex",
                          chatMessage.role === "user" ? "justify-end" : "justify-start",
                        ].join(" ")}
                      >
                        <div
                          className={[
                            "max-w-[78%] rounded-lg px-4 py-3 text-sm leading-7 shadow-lg shadow-black/10",
                            chatMessage.role === "user"
                              ? "bg-violet text-white"
                              : chatMessage.role === "thinking"
                                ? "border border-line bg-panelSoft/80 text-slate-300"
                                : "border border-line bg-panelSoft text-slate-100",
                          ].join(" ")}
                        >
                          {chatMessage.role !== "user" && chatMessage.mode && (
                            <div className="mb-2 text-xs font-bold uppercase tracking-[0.12em] text-violetSoft">
                              {modeLabel(chatMessage.mode)}
                            </div>
                          )}
                          {chatMessage.role === "thinking" ? (
                            <p className="font-bold text-slate-300">{chatMessage.content}</p>
                          ) : chatMessage.role === "assistant" ? (
                            <ReactMarkdown
                              // remark-gfm macht GitHub-Markdown möglich, z.B. Tabellen.
                              remarkPlugins={[remarkGfm]}
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
                                p: ({ children }) => <p className="mb-3 text-slate-100 last:mb-0">{children}</p>,
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
                                table: ({ children }) => (
                                  <div className="my-4 overflow-x-auto rounded-md border border-line">
                                    <table className="w-full border-collapse text-left text-sm">
                                      {children}
                                    </table>
                                  </div>
                                ),
                                thead: ({ children }) => (
                                  <thead className="bg-ink text-slate-100">{children}</thead>
                                ),
                                tbody: ({ children }) => <tbody>{children}</tbody>,
                                tr: ({ children }) => (
                                  <tr className="border-b border-line last:border-b-0">{children}</tr>
                                ),
                                th: ({ children }) => (
                                  <th className="border-r border-line px-3 py-2 font-bold last:border-r-0">
                                    {children}
                                  </th>
                                ),
                                td: ({ children }) => (
                                  <td className="border-r border-line px-3 py-2 align-top last:border-r-0">
                                    {children}
                                  </td>
                                ),
                              }}
                            >
                              {chatMessage.content || "..."}
                            </ReactMarkdown>
                          ) : (
                            <p className="whitespace-pre-wrap">{chatMessage.content}</p>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-400">
                      Die generierte Antwort erscheint hier.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </section>

          <aside className="flex min-h-0 flex-col overflow-hidden border-t border-line bg-panel p-3 lg:border-l lg:border-t-0">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-slate-300">
                Modus
              </h2>
              <div className="mt-3 grid gap-2">
                {modes.map((mode) => (
                  <button
                    key={mode.id}
                    onClick={() => setSelectedMode(mode.id)}
                    className={[
                      "rounded-md border px-3 py-2.5 text-left text-sm font-bold transition",
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

            {isCustomMode && (
              <div className="mt-4 border-t border-line pt-4">
                <h2 className="text-sm font-bold uppercase tracking-[0.16em] text-slate-300">
                  Frage
                </h2>
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Stelle eine eigene Frage zur PDF..."
                  className="mt-3 h-24 w-full resize-none rounded-md border border-line bg-panelSoft px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500"
                />
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="sr-only"
              onChange={(event) => {
                void handleFileSelect(event.target.files?.[0]);
                event.target.value = "";
              }}
            />

            <button
              onClick={handleGenerate}
              disabled={!canGenerate || status === "uploading" || status === "generating"}
              className="mt-4 rounded-md bg-violet px-4 py-2.5 text-sm font-bold text-white transition hover:bg-violetSoft disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status === "generating" ? "Generiert..." : "Generieren"}
            </button>
            <a
              href={`${apiUrl}/download`}
              className={[
                "mt-2 rounded-md border border-line px-4 py-2.5 text-center text-sm font-bold text-slate-100 transition hover:border-violet",
                hasGeneratedAnswer ? "" : "pointer-events-none opacity-50",
              ].join(" ")}
            >
              PDF herunterladen
            </a>
          </aside>
        </div>

        <div className="border-t border-line bg-panel px-4 py-3">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={[
              "flex h-20 w-full cursor-pointer flex-col gap-2 rounded-md border-2 border-dashed px-4 py-3 text-left transition md:flex-row md:items-center md:justify-between",
              isDragging
                ? "border-violet bg-violet/15"
                : "border-line bg-panelSoft hover:border-violet/70",
            ].join(" ")}
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-violet text-xl font-black text-white">
                +
              </div>
              <div className="min-w-0">
                <h2 className="text-sm font-bold text-white">PDF hier ablegen</h2>
                <p className="mt-0.5 text-xs leading-5 text-slate-400">
                  Oder klicken zum Hochladen. Der Pipeline-Fortschritt erscheint hier.
                </p>
                {fileName && (
                  <p className="mt-2 truncate text-xs text-violetSoft">{fileName}</p>
                )}
              </div>
            </div>

            <div className="w-full md:max-w-md">
              <div className="mb-2 flex h-4 items-center justify-between gap-3 text-xs text-slate-300">
                <span>{uploadProgress > 0 ? uploadStageLabel : "Bereit"}</span>
                <span>{uploadProgress > 0 ? `${uploadProgress}%` : ""}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-ink">
                <div
                  className="h-full rounded-full bg-violet transition-all duration-700"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          </button>
        </div>
      </section>
    </main>
  );
}
