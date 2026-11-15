import type { Paper, Source } from "./types";
type Props = {
  source: Source | null;
  setSource: (s: Source | null) => void;
  activeId: string;
  pages: { page_number: number; text: string }[];
  setupPrompt: boolean;
  setSetupPrompt: (v: boolean) => void;
  setView: (v: string) => void;
  deleteTarget: Paper | null;
  setDeleteTarget: (p: Paper | null) => void;
  remove: () => Promise<void>;
  missingModels: string[];
};
export function WorkspaceDialogs({
  source,
  setSource,
  activeId,
  pages,
  setupPrompt,
  setSetupPrompt,
  setView,
  deleteTarget,
  setDeleteTarget,
  remove,
  missingModels,
}: Props) {
  return (
    <>
      {source && (
        <div className="modal-backdrop" onClick={() => setSource(null)}>
          <section
            className="source-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Source evidence"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="row">
              <span className="eyebrow">
                SOURCE EVIDENCE · {source.evidence_id}
              </span>
              <button
                autoFocus
                className="icon-button"
                aria-label="Close evidence"
                onClick={() => setSource(null)}
              >
                ×
              </button>
            </div>
            <h2>{source.paper_title}</h2>
            <span className="badge">
              {source.page_number ? `Page ${source.page_number}` : "Abstract"}
              {source.section ? ` · ${source.section}` : ""}
            </span>
            {source.supporting_quotes?.length ? (
              <>
                <h3>Quoted evidence</h3>
                {source.supporting_quotes.map((quote, i) => (
                  <blockquote key={i}>{quote}</blockquote>
                ))}
                <details>
                  <summary>Passage preview</summary>
                  <p>{source.excerpt}</p>
                </details>
              </>
            ) : (
              <blockquote>{source.excerpt}</blockquote>
            )}
            {source.paper_id === activeId && source.page_number && (
              <details>
                <summary>Read full extracted page</summary>
                <p className="page-text">
                  {pages.find((p) => p.page_number === source.page_number)
                    ?.text ?? "Page text is not available."}
                </p>
              </details>
            )}
            <p className="muted small">
              Check whether this passage supports the interpretation. Valid
              citations alone do not establish scientific correctness.
            </p>
          </section>
        </div>
      )}
      {setupPrompt && (
        <div className="modal-backdrop">
          <section
            className="confirm-modal setup-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Set up local AI"
          >
            <span className="eyebrow">FIRST-RUN SETUP</span>
            <h2>Prepare your local AI</h2>
            <p>
              Install Ollama, then download the selected chat model and the
              local embedding model. Model files download once and are not
              included in the LitLens installer.
            </p>
            <a
              className="setup-link"
              href="https://ollama.com/download/windows"
              target="_blank"
              rel="noreferrer"
            >
              Get Ollama for Windows ↗
            </a>
            <pre>
              {missingModels.map((model) => `ollama pull ${model}`).join("\n")}
            </pre>
            <div className="row">
              <button
                className="secondary"
                onClick={() => {
                  sessionStorage.setItem("litlens.ollama.setup-dismissed", "1");
                  setSetupPrompt(false);
                }}
              >
                Later
              </button>
              <button
                className="primary"
                onClick={() => {
                  sessionStorage.setItem("litlens.ollama.setup-dismissed", "1");
                  setSetupPrompt(false);
                  setView("settings");
                }}
              >
                Open model settings
              </button>
            </div>
          </section>
        </div>
      )}
      {deleteTarget && (
        <div className="modal-backdrop">
          <section
            className="confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Remove paper"
          >
            <h2>Remove this paper?</h2>
            <p>
              “{deleteTarget.title}”, its stored PDF, analysis reports, and chat
              will be removed from your library.
            </p>
            <div className="row">
              <button
                autoFocus
                className="secondary"
                onClick={() => setDeleteTarget(null)}
              >
                Keep paper
              </button>
              <button className="danger-button" onClick={() => void remove()}>
                Remove paper
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
