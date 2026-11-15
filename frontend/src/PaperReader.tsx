import type { Paper } from "./types";
export function PaperReader({
  active,
  readerUrl,
  readerLoading,
}: {
  active: Paper;
  readerUrl: string;
  readerLoading: boolean;
}) {
  return (
    <section className="reader-view">
      <div className="reader-toolbar">
        <div>
          <span className="eyebrow">PAPER READER</span>
          <h2>{active.title}</h2>
        </div>
        {active.source_type === "openalex" && active.pdf_url && (
          <button
            className="secondary"
            onClick={() => void window.litlens?.openExternal(active.pdf_url!)}
          >
            Open publisher PDF ↗
          </button>
        )}
      </div>
      {active.source_type === "upload" ? (
        readerLoading ? (
          <div className="empty">Opening your paper…</div>
        ) : readerUrl ? (
          <iframe
            className="pdf-frame"
            title={`PDF preview: ${active.title}`}
            src={readerUrl}
          />
        ) : (
          <div className="empty">
            <h3>PDF preview unavailable</h3>
            <p>Extracted text is still available under “Extracted text”.</p>
          </div>
        )
      ) : (
        <div className="openalex-reader">
          <div className="chips">
            <span className="chip">OpenAlex record</span>
            {active.publication_year && (
              <span className="chip">{active.publication_year}</span>
            )}
            {active.doi && <span className="chip">DOI · {active.doi}</span>}
          </div>
          <h3>Abstract</h3>
          <p>
            {active.abstract ||
              "OpenAlex does not provide an abstract for this record."}
          </p>
          {active.landing_page_url && (
            <button
              className="secondary"
              onClick={() =>
                void window.litlens?.openExternal(active.landing_page_url!)
              }
            >
              Open publication page ↗
            </button>
          )}
          <p className="muted small">
            This is bibliographic metadata and abstract text. Upload an
            available PDF to read and analyze its full text.
          </p>
        </div>
      )}
    </section>
  );
}
