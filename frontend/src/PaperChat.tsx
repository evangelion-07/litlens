import type { FormEvent, RefObject } from "react";
import type { Preferences, Source, Turn } from "./types";
const readable = (s: string) => s.replaceAll("_", " ");
type Props = {
  settings: Preferences | null;
  useLLM: boolean;
  setUseLLM: (v: boolean) => void;
  asking: boolean;
  turns: Turn[];
  question: string;
  setQuestion: (v: string) => void;
  setSource: (s: Source) => void;
  chatEnd: RefObject<HTMLDivElement | null>;
  ask: (event: FormEvent) => void;
  onClear: () => void;
};
export function PaperChat({
  settings,
  useLLM,
  setUseLLM,
  asking,
  turns,
  question,
  setQuestion,
  setSource,
  chatEnd,
  ask,
  onClear,
}: Props) {
  return (
    <>
      <div className="chat-toolbar">
        <label className="check">
          <input
            type="checkbox"
            checked={useLLM && settings?.provider !== "local"}
            disabled={settings?.provider === "local"}
            onChange={(e) => setUseLLM(e.target.checked)}
          />
          AI answers{" "}
          {settings?.provider === "ollama"
            ? "· Ollama"
            : settings?.provider === "api"
              ? "· external API"
              : "· configure a model in Settings"}
        </label>
        <button className="text-button" disabled={asking} onClick={onClear}>
          Clear chat
        </button>
      </div>
      <div className="chat-messages">
        {!turns.length && (
          <div className="chat-welcome">
            <span>✳</span>
            <h2>What would you like to understand?</h2>
            <p>
              Ask about methods, results, or limitations. Answers stay grounded
              in this paper.
            </p>
            <div className="suggestions">
              {[
                "What methods does this paper use?",
                "What limitations do the authors report?",
                "What are the main findings?",
              ].map((q) => (
                <button key={q} onClick={() => setQuestion(q)}>
                  {q} ↗
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <article className={`chat-message ${t.role}`} key={i}>
            <span className="message-label">
              {t.role === "user"
                ? "YOU"
                : `LITLENS · ${readable(t.answer_mode ?? "evidence")}`}
            </span>
            <p>{t.content}</p>
            {t.citations && (
              <div className="refs">
                {t.citations.map((s) => (
                  <button key={s.evidence_id} onClick={() => setSource(s)}>
                    {s.evidence_id} ·{" "}
                    {s.page_number ? `Page ${s.page_number}` : "Abstract"} ↗
                  </button>
                ))}
              </div>
            )}
            {t.message && <small className="muted">{t.message}</small>}
          </article>
        ))}
        {asking && (
          <div className="thinking">
            <span className="spinner" />
            Retrieving evidence and checking the answer…
          </div>
        )}
        <div ref={chatEnd} />
      </div>
      <form className="chat-composer" onSubmit={ask}>
        <textarea
          aria-label="Question about this paper"
          placeholder="Ask a question about this paper…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          required
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!asking && question.trim().length >= 3)
                e.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <div>
          <small>
            {settings?.provider === "api" && useLLM
              ? "Passages are sent to your configured API provider."
              : "Evidence comes from the selected paper."}
          </small>
          <button
            className="primary"
            disabled={asking || question.trim().length < 3}
          >
            {asking ? "Thinking…" : "Ask →"}
          </button>
        </div>
      </form>
    </>
  );
}
