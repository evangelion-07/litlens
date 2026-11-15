import type { Report, Source, SupportingQuote } from "./types";

export function ReportView({
  report,
  onSource,
}: {
  report: Report;
  onSource: (s: Source) => void;
}) {
  /** Collect every supporting quote for a given evidence_id across the report. */
  const quotesForEvidence = (evidenceId: string): string[] => {
    const quotes: string[] = [];
    const collect = (items: { supporting_quotes?: SupportingQuote[] }[]) => {
      for (const item of items) {
        for (const sq of item.supporting_quotes ?? []) {
          if (sq.evidence_id === evidenceId && !quotes.includes(sq.quote)) {
            quotes.push(sq.quote);
          }
        }
      }
    };
    collect([report.executive_summary]);
    collect(report.key_findings);
    collect(report.strengths);
    collect(report.weaknesses);
    collect(report.recommendations);
    collect(report.research_gaps);
    collect(report.priority_action_plan);
    return quotes;
  };
  const refs = (ids: string[], quotes: SupportingQuote[] = []) => (
    <span className="refs">
      {ids.map((id) => {
        const source = report.evidence.find((s) => s.evidence_id === id);
        return source ? (
          <button
            key={id}
            title={`Open evidence ${id}`}
            onClick={() =>
              onSource({
                ...source,
                supporting_quotes: quotes
                  .filter((q) => q.evidence_id === id)
                  .map((q) => q.quote),
              })
            }
          >
            {source.page_number ? `p. ${source.page_number}` : "Abstract"} ·{" "}
            {id}
          </button>
        ) : null;
      })}
    </span>
  );
  const claims = (title: string, items: Report["key_findings"]) => (
    <section className="report-section">
      <h3>{title}</h3>
      {items.length ? (
        items.map((item, i) => (
          <div className="insight" key={i}>
            <p>{item.text}</p>
            {refs(item.evidence_ids, item.supporting_quotes)}
          </div>
        ))
      ) : (
        <p className="muted">Not established from the available evidence.</p>
      )}
    </section>
  );
  return (
    <div className="report-body">
      <div className="coverage">
        <div>
          <span className="eyebrow">TEXT COVERAGE</span>
          <h3>{report.coverage.scope.replaceAll("_", " ")}</h3>
        </div>
        <div>
          <strong>
            {report.coverage.pages_analyzed}/{report.coverage.total_pages}
          </strong>
          <small>pages with evidence</small>
        </div>
        <div>
          <strong>{report.coverage.analyzed_units}</strong>
          <small>evidence chunks</small>
        </div>
      </div>
      <p className="muted small">{report.coverage.note}</p>
      <div className="chips">
        <span className="chip">
          {report.analysis_mode.replaceAll("_", " ")}
        </span>
        <span className="chip">
          {report.retrieval?.mode.replaceAll("_", " ") ?? "Keyword"} retrieval
        </span>
      </div>
      <section className="report-section">
        <span className="eyebrow">THE BIG PICTURE</span>
        <h2>Executive summary</h2>
        <p className="lead">{report.executive_summary.text}</p>
        {refs(
          report.executive_summary.evidence_ids,
          report.executive_summary.supporting_quotes,
        )}
      </section>
      {claims("Key findings", report.key_findings)}
      {claims("Strengths", report.strengths)}
      <section className="report-section">
        <h3>Limitations & review concerns</h3>
        {report.weaknesses.length ? (
          report.weaknesses.map((item, i) => (
            <div className="insight" key={i}>
              <span className="badge amber">
                {item.classification.replaceAll("_", " ")}
              </span>
              <h4>{item.statement}</h4>
              <p>{item.why_it_matters}</p>
              <p>
                <strong>Next step:</strong> {item.recommendation}
              </p>
              {refs(item.evidence_ids, item.supporting_quotes)}
            </div>
          ))
        ) : (
          <p className="muted">
            No explicit limitation was extracted. This does not establish that
            the paper has none.
          </p>
        )}
      </section>
      <section className="report-section">
        <h3>Recommendations</h3>
        {report.recommendations.map((item, i) => (
          <div className="insight" key={i}>
            <span className="badge">{item.basis.replaceAll("_", " ")}</span>
            <h4>{item.change}</h4>
            <p>{item.why}</p>
            <p>
              <strong>How:</strong> {item.how}
            </p>
            <small>{item.expected_benefit}</small>
            {refs(item.evidence_ids, item.supporting_quotes)}
          </div>
        ))}
      </section>
      <section className="report-section">
        <h3>Research directions</h3>
        {report.research_gaps.length ? (
          report.research_gaps.map((item, i) => (
            <div className="insight" key={i}>
              <span className="badge amber">{item.confidence} confidence</span>
              <h4>{item.statement}</h4>
              <p>{item.research_question}</p>
              <small>{item.scope_note}</small>
              {refs(item.evidence_ids, item.supporting_quotes)}
            </div>
          ))
        ) : (
          <p className="muted">
            No supported direction was identified. Novelty requires a broader
            literature review.
          </p>
        )}
      </section>
      <section className="report-section">
        <h3>Priority action plan</h3>
        {report.priority_action_plan.map((item, i) => (
          <div className="action-step" key={i}>
            <span>{i + 1}</span>
            <div>
              <h4>{item.action}</h4>
              <p>{item.rationale}</p>
              {refs(item.evidence_ids, item.supporting_quotes)}
            </div>
          </div>
        ))}
      </section>
      <details className="panel">
        <summary>Section-by-section analysis</summary>
        {Object.entries(report.section_summaries).map(([name, s]) => (
          <div className="insight" key={name}>
            <h4>{name.replaceAll("_", " ")}</h4>
            <p>{s.summary}</p>
            {refs(s.evidence_ids)}
          </div>
        ))}
      </details>
      <details className="panel">
        <summary>Evidence register · {report.evidence.length} passages</summary>
        {report.evidence.map((s) => {
          const quotes = quotesForEvidence(s.evidence_id);
          return (
            <button
              className="evidence-row"
              key={s.evidence_id}
              onClick={() =>
                onSource({
                  ...s,
                  supporting_quotes: quotes.length ? quotes : undefined,
                })
              }
            >
              <strong>
                {s.evidence_id} · {s.section} ·{" "}
                {s.page_number ? `Page ${s.page_number}` : "Abstract"}
              </strong>
              <p>{s.excerpt}</p>
            </button>
          );
        })}
      </details>
      <aside className="caveats">
        <strong>Interpretation limits</strong>
        <ul>
          {report.caveats.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
