import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, download, hasToken, json, request, setToken } from "./api";
import { AccountView } from "./AccountView";
import { SettingsView } from "./SettingsView";
import { PaperReader } from "./PaperReader";
import { PaperChat } from "./PaperChat";
import { WorkspaceDialogs } from "./WorkspaceDialogs";
import { ReportView } from "./ReportView";
import type {
  Answer,
  Job,
  ModelStatus,
  Paper,
  Preferences,
  Source,
  Turn,
  User,
} from "./types";
import "./styles.css";

type SearchPaper = {
  openalex_id: string;
  title: string;
  authors: string[];
  year: number;
  doi?: string;
  abstract?: string;
  landing_page_url?: string;
  pdf_url?: string;
  open_access: boolean;
};
type Comparison = {
  papers: {
    paper_id: string;
    title: string;
    sections: Record<string, { text: string; page_numbers: number[] }>;
  }[];
  analysis_note: string;
};
const readable = (s: string) => s.replaceAll("_", " ");

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(hasToken());
  useEffect(() => {
    if (hasToken())
      void api<User>("/auth/me")
        .then(setUser)
        .catch(() => setToken(""))
        .finally(() => setLoading(false));
    const out = () => setUser(null);
    window.addEventListener("litlens:signed-out", out);
    return () => window.removeEventListener("litlens:signed-out", out);
  }, []);
  if (loading)
    return (
      <div className="loading-screen">
        <span className="logo">L</span>
        <p>Opening your workspace…</p>
      </div>
    );
  return user ? (
    <Workspace key={user.id} user={user} onLogout={() => setUser(null)} />
  ) : (
    <AccountView onLogin={setUser} />
  );
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [view, setView] = useState("library");
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    localStorage.getItem("litlens.theme") === "dark" ? "dark" : "light",
  );
  const [papers, setPapers] = useState<Paper[]>([]);
  const [settings, setSettings] = useState<Preferences | null>(null);
  const [activeId, setActiveId] = useState("");
  const activeRef = useRef(activeId);
  activeRef.current = activeId;
  const [selected, setSelected] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [tab, setTab] = useState("report");
  const [job, setJob] = useState<Job | null>(null);
  const [historyJobId, setHistoryJobId] = useState("");
  const [history, setHistory] = useState<Job[]>([]);
  const [pages, setPages] = useState<{ page_number: number; text: string }[]>(
    [],
  );
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [useLLM, setUseLLM] = useState(true);
  const [asking, setAsking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pollError, setPollError] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Paper | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchPaper[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [comparing, setComparing] = useState(false);
  const [readerUrl, setReaderUrl] = useState("");
  const [readerLoading, setReaderLoading] = useState(false);
  const [setupPrompt, setSetupPrompt] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const chatEnd = useRef<HTMLDivElement>(null);
  const active = papers.find((p) => p.id === activeId);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("litlens.theme", theme);
  }, [theme]);
  useEffect(() => {
    if (!settings) return;
    const localModelsRequired =
      settings.provider === "ollama" || settings.embeddings_enabled;
    let cancelled = false;
    async function checkModels() {
      try {
        const result = await api<ModelStatus>("/settings/models");
        if (cancelled) return;
        setModelStatus(result);
        if (
          localModelsRequired &&
          !result.ready &&
          sessionStorage.getItem("litlens.ollama.setup-dismissed") !== "1"
        )
          setSetupPrompt(true);
      } catch {
        if (!cancelled) setModelStatus(null);
      }
    }
    void checkModels();
    const timer = setInterval(checkModels, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [settings]);
  async function refresh() {
    const [library, records] = await Promise.all([
      api<{ results: Paper[] }>("/library/papers"),
      api<Job[]>("/analysis/history"),
    ]);
    setPapers(library.results);
    setHistory(records);
    setSelected((ids) =>
      ids.filter((id) => library.results.some((p) => p.id === id)),
    );
  }
  useEffect(() => {
    void Promise.all([
      refresh(),
      api<Preferences>("/settings").then(setSettings),
    ]).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    let cancelled = false;
    setJob(null);
    setPages([]);
    setTurns([]);
    setQuestion("");
    setSource(null);
    setPollError("");
    setAsking(false);
    if (!activeId) return;
    void api<Job>(
      historyJobId
        ? `/analysis/${historyJobId}`
        : `/analysis/papers/${activeId}/latest`,
    )
      .then((j) => {
        if (!cancelled) setJob(j);
      })
      .catch((e) => {
        if (!cancelled && !e.message.includes("No analysis history"))
          setError(e.message);
      });
    void api<{ pages: typeof pages }>(`/library/papers/${activeId}/pages`)
      .then((r) => {
        if (!cancelled) setPages(r.pages);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    void api<{ turns: Turn[] }>(`/assistant/history?paper_id=${activeId}`)
      .then((r) => {
        if (!cancelled) setTurns(r.turns);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [activeId, historyJobId]);
  useEffect(() => {
    let disposed = false;
    let url = "";
    setReaderUrl("");
    if (!active || active.source_type !== "upload") return;
    setReaderLoading(true);
    void request(`/library/papers/${active.id}/pdf`)
      .then(async (response) => {
        const blob = await response.blob();
        if (disposed) return;
        url = URL.createObjectURL(blob);
        setReaderUrl(url);
      })
      .catch(() => {
        if (!disposed) setReaderUrl("");
      })
      .finally(() => {
        if (!disposed) setReaderLoading(false);
      });
    return () => {
      disposed = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [active?.id, active?.source_type]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const id = job.analysis_id;
    async function poll() {
      let complete = false;
      try {
        const next = await api<Job>(`/analysis/${id}`);
        if (stopped) return;
        setJob(next);
        setPollError("");
        complete = ["completed", "failed"].includes(next.status);
        if (complete) await refresh();
      } catch (e) {
        if (!stopped)
          setPollError(
            `Status refresh interrupted. Retrying… ${(e as Error).message}`,
          );
      } finally {
        if (!stopped && !complete) timer = setTimeout(poll, 1500);
      }
    }
    timer = setTimeout(poll, 600);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [job?.analysis_id, job?.status]);
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns, asking]);
  useEffect(() => {
    if (!source && !deleteTarget) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSource(null);
        setDeleteTarget(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [source, deleteTarget]);

  function choosePaper(id: string) {
    setHistoryJobId("");
    setActiveId(id);
    setTab("report");
  }
  async function upload(file?: File) {
    if (!file || uploading) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Choose a PDF document.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError("Choose a PDF smaller than 20 MB.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const result = await api<{
        paper_id: string;
        title: string;
        analysis?: Job;
      }>(`/library/upload?filename=${encodeURIComponent(file.name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/pdf" },
        body: file,
      });
      await refresh();
      choosePaper(result.paper_id);
      setView("library");
      setNotice(
        `${result.title} added. ${result.analysis ? "Analysis has started." : "Ready to analyze."}`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }
  async function analyze() {
    if (!active || starting) return;
    const paperId = active.id;
    setStarting(true);
    setError("");
    try {
      const next = await api<Job>(
        `/analysis/papers/${paperId}`,
        json({ use_external_ai: settings?.provider !== "local" }),
      );
      if (activeRef.current === paperId) {
        setJob(next);
        setTab("report");
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  }
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!active || asking) return;
    const paperId = active.id;
    const text = question.trim();
    if (text.length < 3) return;
    const previous = turns;
    setAsking(true);
    setError("");
    setQuestion("");
    setTurns([...previous, { role: "user", content: text }]);
    try {
      const result = await api<Answer>(
        "/assistant/ask",
        json({
          question: text,
          paper_ids: [paperId],
          use_llm: useLLM && settings?.provider !== "local",
          top_k: 8,
          conversation: previous
            .slice(-8)
            .map((t) => ({ role: t.role, content: t.content.slice(0, 12000) })),
        }),
      );
      if (activeRef.current === paperId)
        setTurns((t) => [
          ...t,
          {
            role: "assistant",
            content: result.answer,
            citations: result.citations,
            answer_mode: result.answer_mode,
            retrieval_mode: result.retrieval_mode,
            message: result.message,
          },
        ]);
    } catch (e) {
      if (activeRef.current === paperId) {
        setError((e as Error).message);
        setTurns(previous);
        setQuestion(text);
      }
    } finally {
      if (activeRef.current === paperId) setAsking(false);
    }
  }
  async function remove() {
    if (!deleteTarget) return;
    try {
      await api(`/library/papers/${deleteTarget.id}`, { method: "DELETE" });
      if (activeId === deleteTarget.id) setActiveId("");
      await refresh();
      setNotice("Paper and its reports removed.");
      setDeleteTarget(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function search(event: FormEvent) {
    event.preventDefault();
    setSearching(true);
    setError("");
    setSearched(true);
    try {
      const r = await api<{ results: SearchPaper[] }>(
        `/papers/search?q=${encodeURIComponent(query)}&per_page=20`,
      );
      setResults(r.results);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSearching(false);
    }
  }
  async function savePaper(paper: SearchPaper) {
    try {
      await api("/library/papers", json(paper));
      await refresh();
      setNotice("Paper metadata saved. Upload a PDF for full-text analysis.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function compare() {
    setComparing(true);
    setError("");
    try {
      setComparison(
        await api("/library/compare", json({ paper_ids: selected })),
      );
      setView("compare");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setComparing(false);
    }
  }
  async function exportReport(format: string) {
    if (!job) return;
    try {
      await download(
        `/analysis/${job.analysis_id}/export?format=${format}`,
        `${active?.title ?? "paper"}-analysis.${format === "pdf" ? "pdf" : "md"}`,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function signOut() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* Local logout still clears the credential. */
    }
    setToken("");
    onLogout();
  }

  return (
    <div className="desktop-layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">L</span>
          <span>LitLens</span>
        </div>
        <small className="edition">RESEARCH WORKSPACE</small>
        <button
          className="primary upload-button"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
        >
          {uploading ? "Processing PDF…" : "+ Import a paper"}
        </button>
        <input
          hidden
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={(e) => void upload(e.target.files?.[0])}
        />
        <nav aria-label="Workspace navigation">
          {[
            ["library", "▤", "My library"],
            ["discover", "⌕", "Discover papers"],
            ["compare", "⇄", "Compare"],
            ["history", "◷", "Analysis history"],
            ["reader", "▣", "Paper reader"],
            ["assistant", "✳", "Paper assistant"],
          ].map(([id, icon, label]) => (
            <button
              key={id}
              className={
                view === id ||
                (id === "assistant" && view === "library" && tab === "chat") ||
                (id === "reader" && view === "library" && tab === "reader")
                  ? "active"
                  : ""
              }
              onClick={() => {
                if (id === "assistant" || id === "reader") {
                  if (!activeId && papers[0]) setActiveId(papers[0].id);
                  setView("library");
                  setTab(id === "assistant" ? "chat" : "reader");
                } else setView(id);
              }}
            >
              <span>{icon}</span>
              {label}
              {id === "library" && <small>{papers.length}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            className={
              view === "settings" ? "nav-settings active" : "nav-settings"
            }
            onClick={() => setView("settings")}
          >
            ⚙ &nbsp; Models & preferences
          </button>
          <div className="profile">
            <span className="avatar">{user.display_name[0].toUpperCase()}</span>
            <div>
              <strong>{user.display_name}</strong>
              <small>@{user.username}</small>
            </div>
            <button
              title="Sign out"
              aria-label="Sign out"
              onClick={() => void signOut()}
            >
              ↪
            </button>
          </div>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <span>/</span>
            <strong>
              {view === "library"
                ? "My library"
                : view === "settings"
                  ? "Models & preferences"
                  : view === "assistant"
                    ? "Paper assistant"
                    : readable(view)}
            </strong>
          </div>
          <div className="topbar-actions">
            <button
              className="theme-toggle"
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
              title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            >
              {theme === "light" ? "☾" : "☼"}
              <span>{theme === "light" ? "Dark" : "Light"}</span>
            </button>
            <span className="animated-brand-mark" title="LitLens">
              <span className="logo">L</span>
              <i />
            </span>
            <span
              className={`model-indicator ${modelStatus?.ready ? "ready" : "unready"}`}
              title={modelStatus?.message ?? "Checking selected local models"}
            >
              <i />
              {settings?.provider === "ollama"
                ? `Ollama · ${settings.ollama_model}`
                : settings?.provider === "api"
                  ? `API · ${settings.api_model}`
                  : "Local evidence"}
              {!modelStatus
                ? " · checking"
                : !modelStatus.available
                  ? " · Ollama offline"
                  : !modelStatus.chat_ready && settings?.provider === "ollama"
                    ? ` · chat model missing`
                    : !modelStatus.embeddings_ready && settings?.embeddings_enabled
                      ? ` · embedding model missing`
                      : !modelStatus.ready
                        ? " · setup needed"
                        : settings?.provider === "api"
                          ? " · configured"
                          : ""}
            </span>
          </div>
        </header>
        {error && (
          <div role="alert" className="toast error">
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              ×
            </button>
          </div>
        )}
        {notice && (
          <div role="status" className="toast success">
            {notice}
            <button
              aria-label="Dismiss notification"
              onClick={() => setNotice("")}
            >
              ×
            </button>
          </div>
        )}
        {view === "library" && (
          <div className="library-layout">
            <section className="library-pane">
              <div className="pane-heading">
                <span className="eyebrow">YOUR COLLECTION</span>
                <h2>
                  My library <small>{papers.length}</small>
                </h2>
                <input
                  className="search-input"
                  placeholder="Filter your papers…"
                  aria-label="Filter papers"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                />
              </div>
              <div
                className="paper-list"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  void upload(e.dataTransfer.files[0]);
                }}
              >
                {papers
                  .filter((p) =>
                    p.title.toLowerCase().includes(filter.toLowerCase()),
                  )
                  .map((p) => (
                    <article
                      className={`paper-card ${activeId === p.id ? "selected" : ""}`}
                      key={p.id}
                    >
                      <div className="paper-card-top">
                        <span className="paper-icon">
                          {p.source_type === "upload" ? "PDF" : "OA"}
                        </span>
                        <label className="select-paper">
                          <input
                            type="checkbox"
                            aria-label={`Select ${p.title} for comparison`}
                            checked={selected.includes(p.id)}
                            disabled={
                              !selected.includes(p.id) && selected.length >= 5
                            }
                            onChange={() => {
                              setComparison(null);
                              setSelected((ids) =>
                                ids.includes(p.id)
                                  ? ids.filter((x) => x !== p.id)
                                  : [...ids, p.id],
                              );
                            }}
                          />
                        </label>
                      </div>
                      <button
                        className="paper-open"
                        onClick={() => choosePaper(p.id)}
                      >
                        <h3>{p.title}</h3>
                        <p>
                          {p.authors.slice(0, 2).join(", ") ||
                            "Author not available"}
                        </p>
                        <div className="paper-meta">
                          <span>
                            {p.page_count
                              ? `${p.page_count} pages`
                              : "Metadata only"}
                          </span>
                          <span
                            className={`badge ${p.latest_analysis_status === "completed" ? "green" : ""}`}
                          >
                            {readable(
                              p.latest_analysis_status ?? p.processing_status,
                            )}
                          </span>
                        </div>
                      </button>
                    </article>
                  ))}
                {papers.length === 0 && (
                  <div className="empty-library">
                    <span>↥</span>
                    <h3>Your next idea starts here.</h3>
                    <p>
                      Import a research PDF or discover a paper. You can also
                      drop a PDF here.
                    </p>
                    <button
                      className="secondary"
                      onClick={() => fileRef.current?.click()}
                    >
                      Choose a PDF
                    </button>
                  </div>
                )}
              </div>
              {selected.length > 0 && (
                <div className="selection-bar">
                  <small>{selected.length}/5 selected</small>
                  <button
                    className="secondary"
                    disabled={selected.length < 2 || comparing}
                    onClick={() => void compare()}
                  >
                    {comparing ? "Comparing…" : "Compare →"}
                  </button>
                </div>
              )}
            </section>
            <section className="paper-workspace">
              {!active ? (
                <div className="welcome">
                  <span className="welcome-glyph">✳</span>
                  <span className="eyebrow">
                    LESS SEARCHING. MORE UNDERSTANDING.
                  </span>
                  <h1>
                    A clearer view
                    <br />
                    of your research.
                  </h1>
                  <p>
                    Select a paper to read its analysis, inspect the evidence,
                    or start a conversation.
                  </p>
                  <div className="welcome-steps">
                    <div>
                      <b>01</b>
                      <strong>Bring your paper</strong>
                      <span>Upload a readable PDF.</span>
                    </div>
                    <div>
                      <b>02</b>
                      <strong>Follow the analysis</strong>
                      <span>Review findings and limitations.</span>
                    </div>
                    <div>
                      <b>03</b>
                      <strong>Ask with evidence</strong>
                      <span>Open the passage behind an answer.</span>
                    </div>
                  </div>
                  <button
                    className="primary"
                    disabled={uploading}
                    onClick={() => fileRef.current?.click()}
                  >
                    {papers.length
                      ? "Import another paper →"
                      : "Import your first paper →"}
                  </button>
                </div>
              ) : (
                <>
                  <header className="paper-header">
                    <div className="row">
                      <span className="eyebrow">
                        {active.source_type === "upload"
                          ? "RESEARCH PAPER"
                          : "SCHOLARLY RECORD"}
                      </span>
                      <button
                        className="icon-button danger"
                        title="Remove paper"
                        aria-label="Remove paper"
                        onClick={() => setDeleteTarget(active)}
                      >
                        ×
                      </button>
                    </div>
                    <h1>{active.title}</h1>
                    <p>
                      {active.authors.join(", ") ||
                        "Author metadata unavailable"}
                      {active.publication_year
                        ? ` · ${active.publication_year}`
                        : ""}
                    </p>
                    <div className="paper-actions">
                      <button
                        className="primary"
                        disabled={
                          starting ||
                          ["queued", "running"].includes(job?.status ?? "")
                        }
                        onClick={() => void analyze()}
                      >
                        {starting
                          ? "Starting…"
                          : job?.status === "running" ||
                              job?.status === "queued"
                            ? "Analysis in progress"
                            : job?.report
                              ? "Analyze again"
                              : "Analyze paper"}
                      </button>
                      {job?.report && (
                        <>
                          <button
                            className="secondary"
                            onClick={() => void exportReport("pdf")}
                          >
                            Export PDF ↓
                          </button>
                          <button
                            className="text-button"
                            onClick={() => void exportReport("markdown")}
                          >
                            Markdown
                          </button>
                        </>
                      )}
                    </div>
                  </header>
                  <div className="tabs" role="tablist">
                    {[
                      ["report", "Analysis"],
                      ["chat", "Ask this paper"],
                      ["reader", "Read paper"],
                      ["pages", "Extracted text"],
                    ].map(([id, label]) => (
                      <button
                        role="tab"
                        aria-selected={tab === id}
                        className={tab === id ? "active" : ""}
                        key={id}
                        onClick={() => setTab(id)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div
                    className={`paper-content ${tab === "chat" ? "chat-content" : ""}`}
                  >
                    {tab === "report" && (
                      <>
                        {job && ["queued", "running"].includes(job.status) && (
                          <div className="analysis-progress">
                            <span className="spinner" />
                            <h3>Reading your paper</h3>
                            <p>{job.stage}</p>
                            <progress max={100} value={job.progress} />
                            <small>
                              {job.progress}% · You can keep browsing your
                              library.
                            </small>
                          </div>
                        )}
                        {pollError && <p className="error">{pollError}</p>}
                        {job?.error && <p className="error">{job.error}</p>}
                        {job?.report ? (
                          <ReportView
                            report={job.report}
                            onSource={setSource}
                          />
                        ) : (
                          !["queued", "running"].includes(
                            job?.status ?? "",
                          ) && (
                            <div className="empty">
                              <h3>
                                {active.processing_status === "no_text"
                                  ? "This PDF needs readable text."
                                  : "Ready for a closer look."}
                              </h3>
                              <p>
                                {active.processing_message ||
                                  "Analyze this paper for a section-by-section report, findings, limitations, and research directions."}
                              </p>
                              <p className="muted">
                                {settings?.provider === "api"
                                  ? "Your configured API provider will receive extracted text."
                                  : settings?.provider === "ollama"
                                    ? "Ollama runs locally. If it is unavailable, a local extractive report is saved."
                                    : "Evidence-only mode creates a local extractive report."}
                              </p>
                            </div>
                          )
                        )}
                      </>
                    )}
                    {tab === "reader" && (
                      <PaperReader
                        active={active}
                        readerUrl={readerUrl}
                        readerLoading={readerLoading}
                      />
                    )}
                    {tab === "pages" && (
                      <div className="extracted-pages">
                        {pages.length ? (
                          pages.map((p) => (
                            <details
                              className="panel"
                              key={p.page_number}
                              open={pages.length === 1}
                            >
                              <summary>Page {p.page_number}</summary>
                              <p className="page-text">
                                {p.text ||
                                  "No readable text was extracted from this page."}
                              </p>
                            </details>
                          ))
                        ) : (
                          <div className="empty">
                            <h3>Metadata record</h3>
                            <p>
                              {active.abstract ||
                                "Upload the full PDF to inspect page-level evidence."}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                    {tab === "chat" && (
                      <PaperChat
                        settings={settings}
                        useLLM={useLLM}
                        setUseLLM={setUseLLM}
                        asking={asking}
                        turns={turns}
                        question={question}
                        setQuestion={setQuestion}
                        setSource={setSource}
                        chatEnd={chatEnd}
                        ask={ask}
                        onClear={() => {
                          void api(`/assistant/history?paper_id=${active.id}`, {
                            method: "DELETE",
                          })
                            .then(() => {
                              if (activeRef.current === active.id) setTurns([]);
                            })
                            .catch((e) => setError(e.message));
                        }}
                      />
                    )}
                  </div>
                </>
              )}
            </section>
          </div>
        )}
        {view === "settings" &&
          (settings ? (
            <SettingsView
              settings={settings}
              onChange={setSettings}
              onRestore={refresh}
            />
          ) : (
            <div className="empty">Loading preferences…</div>
          ))}
        {view === "discover" && (
          <div className="full-page">
            <div className="page-heading">
              <span className="eyebrow">EXPAND YOUR READING</span>
              <h1>Discover research</h1>
              <p>
                Search OpenAlex for papers, abstracts, and publication links.
              </p>
            </div>
            <form className="discovery-search" onSubmit={search}>
              <input
                aria-label="Research topic"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Try plant disease detection or retrieval augmented generation"
                minLength={2}
                maxLength={200}
                required
              />
              <button className="primary" disabled={searching}>
                {searching ? "Searching…" : "Search papers →"}
              </button>
            </form>
            <div className="search-results">
              {results.map((p) => (
                <article className="panel search-result" key={p.openalex_id}>
                  <div className="row">
                    <span className="badge">
                      {p.year ?? "Year unavailable"} · OpenAlex
                    </span>
                    <span className="muted small">
                      {p.open_access
                        ? "Open access reported"
                        : "Check availability"}
                    </span>
                  </div>
                  <h2>{p.title}</h2>
                  <p className="muted">{p.authors.slice(0, 5).join(", ")}</p>
                  <p>
                    {p.abstract ?? "No abstract is available for this record."}
                  </p>
                  <div className="row">
                    <button
                      className="secondary"
                      disabled={papers.some((x) => !!p.doi && x.doi === p.doi)}
                      onClick={() => void savePaper(p)}
                    >
                      Save metadata
                    </button>
                    {p.landing_page_url &&
                      /^https?:\/\//i.test(p.landing_page_url) && (
                        <a
                          target="_blank"
                          rel="noreferrer"
                          href={p.landing_page_url}
                        >
                          Publication page ↗
                        </a>
                      )}
                  </div>
                </article>
              ))}
              {searched && !searching && results.length === 0 && (
                <div className="empty">
                  No results to show. Try another topic.
                </div>
              )}
            </div>
          </div>
        )}
        {view === "history" && (
          <div className="full-page">
            <div className="page-heading">
              <span className="eyebrow">PICK UP WHERE YOU LEFT OFF</span>
              <h1>Analysis history</h1>
              <p>Saved reports and their processing status.</p>
            </div>
            {history.length ? (
              history.map((j) => (
                <article className="panel history-row" key={j.analysis_id}>
                  <div>
                    <span
                      className={`badge ${j.status === "completed" ? "green" : ""}`}
                    >
                      {j.status}
                    </span>
                    <h3>{j.paper_title}</h3>
                    <small>
                      {new Date(j.updated_at).toLocaleString()} · {j.stage}
                    </small>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => {
                      setActiveId(j.paper_id);
                      setHistoryJobId(j.analysis_id);
                      setTab("report");
                      setView("library");
                    }}
                  >
                    Open report →
                  </button>
                </article>
              ))
            ) : (
              <div className="empty">
                Upload and analyze a paper to start your history.
              </div>
            )}
          </div>
        )}
        {view === "compare" && (
          <div className="full-page">
            <div className="page-heading">
              <span className="eyebrow">CONNECT THE FINDINGS</span>
              <h1>Compare papers</h1>
              <p>
                Select two to five papers using the checkboxes in your library.
              </p>
            </div>
            <button
              className="primary"
              disabled={selected.length < 2 || comparing}
              onClick={() => void compare()}
            >
              {comparing
                ? "Comparing…"
                : `Compare ${selected.length} selected papers`}
            </button>
            {comparison ? (
              <>
                <p className="muted">{comparison.analysis_note}</p>
                <div className="comparison-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Dimension</th>
                        {comparison.papers.map((p) => (
                          <th key={p.paper_id}>{p.title}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        "objective",
                        "methods",
                        "datasets",
                        "experimental_design",
                        "baselines",
                        "evaluation_metrics",
                        "findings",
                        "strengths",
                        "limitations",
                        "research_gaps",
                        "future_work",
                      ].map((field) => (
                        <tr key={field}>
                          <th>{readable(field)}</th>
                          {comparison.papers.map((p) => (
                            <td key={p.paper_id}>
                              {p.sections[field] ? (
                                <>
                                  <p>{p.sections[field].text}</p>
                                  <small>
                                    Pages:{" "}
                                    {p.sections[field].page_numbers.join(
                                      ", ",
                                    ) || "Abstract"}
                                  </small>
                                </>
                              ) : (
                                <span className="muted">
                                  Not detected in available text
                                </span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="empty">
                Compare methods, datasets, results, and limitations side by
                side.
              </div>
            )}
          </div>
        )}
      </main>
      <WorkspaceDialogs
        source={source}
        setSource={setSource}
        activeId={activeId}
        pages={pages}
        setupPrompt={setupPrompt}
        setSetupPrompt={setSetupPrompt}
        setView={setView}
        deleteTarget={deleteTarget}
        setDeleteTarget={setDeleteTarget}
        remove={remove}
        missingModels={modelStatus?.missing_models ?? []}
      />
    </div>
  );
}

export default App;
