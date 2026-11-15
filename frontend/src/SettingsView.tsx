import { useEffect, useState, type FormEvent } from "react";
import { api, json } from "./api";
import { BackupPanel } from "./BackupPanel";
import type { ModelStatus, Preferences } from "./types";

export function SettingsView({
  settings,
  onChange,
  onRestore,
}: {
  settings: Preferences;
  onChange: (s: Preferences) => void;
  onRestore: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(settings);
  const [openalexKey, setOpenalexKey] = useState("");
  const [clearOpenalex, setClearOpenalex] = useState(false);
  const [key, setKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
  const [models, setModels] = useState<ModelStatus | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const installed = (name: string) =>
    models?.models.some(
      (model) => model.name === name || model.name === `${name}:latest`,
    ) ?? false;
  async function refresh() {
    try {
      setModels(await api("/settings/models"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const s = await api<Preferences>(
        "/settings",
        json(
          {
            ...draft,
            api_key: key || null,
            clear_api_key: clearKey,
            openalex_api_key: openalexKey || null,
            clear_openalex_api_key: clearOpenalex,
          },
          "PUT",
        ),
      );
      onChange(s);
      setDraft(s);
      setKey("");
      setClearKey(false);
      setOpenalexKey("");
      setClearOpenalex(false);
      setMessage("Preferences saved for your account.");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="settings-page">
      <div className="page-heading">
        <span className="eyebrow">MAKE IT YOURS</span>
        <h1>Models & preferences</h1>
        <p>Choose how LitLens reads, retrieves, and explains your papers.</p>
      </div>
      <form onSubmit={save}>
        <section className="panel">
          <h2>Answering & analysis</h2>
          <p className="muted">
            This choice is used for automatic reports and for chat when AI
            answers is enabled.
          </p>
          <div className="provider-grid">
            {(["ollama", "api", "local"] as const).map((p) => (
              <button
                type="button"
                className={`provider-card ${draft.provider === p ? "selected" : ""}`}
                key={p}
                onClick={() => setDraft({ ...draft, provider: p })}
              >
                <strong>
                  {p === "ollama"
                    ? "Ollama · local AI"
                    : p === "api"
                      ? "API provider"
                      : "Evidence only"}
                </strong>
                <span>
                  {p === "ollama"
                    ? "Runs on your computer. No API key."
                    : p === "api"
                      ? "Send passages to your chosen service."
                      : "Extractive reports and quoted passages."}
                </span>
              </button>
            ))}
          </div>
          {draft.provider === "ollama" && (
            <div className="field-grid">
              <label>
                Chat model
                <input
                  list="ollama-models"
                  value={draft.ollama_model}
                  onChange={(e) =>
                    setDraft({ ...draft, ollama_model: e.target.value })
                  }
                  required
                />
              </label>
              <label>
                Ollama address
                <input
                  value={draft.ollama_url}
                  onChange={(e) =>
                    setDraft({ ...draft, ollama_url: e.target.value })
                  }
                  required
                />
              </label>
            </div>
          )}
          {draft.provider === "api" && (
            <div className="api-settings">
              <label>
                HTTPS chat-completions endpoint
                <input
                  type="url"
                  placeholder="https://provider.example/v1/chat/completions"
                  value={draft.api_url}
                  onChange={(e) =>
                    setDraft({ ...draft, api_url: e.target.value })
                  }
                  required
                />
              </label>
              <div className="field-grid">
                <label>
                  Model ID
                  <input
                    value={draft.api_model}
                    onChange={(e) =>
                      setDraft({ ...draft, api_model: e.target.value })
                    }
                    required
                  />
                </label>
                <label>
                  API key
                  <input
                    type="password"
                    autoComplete="off"
                    placeholder={
                      draft.has_api_key
                        ? "Saved securely · leave blank to keep"
                        : "Paste your provider key here"
                    }
                    value={key}
                    onChange={(e) => setKey(e.target.value)}
                  />
                </label>
              </div>
              {draft.has_api_key && (
                <label className="check">
                  <input
                    type="checkbox"
                    checked={clearKey}
                    onChange={(e) => setClearKey(e.target.checked)}
                  />
                  Remove the saved key
                </label>
              )}
              <label className="check consent">
                <input
                  type="checkbox"
                  checked={draft.allow_external_ai}
                  onChange={(e) =>
                    setDraft({ ...draft, allow_external_ai: e.target.checked })
                  }
                  required
                />
                I allow paper passages and questions to be sent to this API
                provider.
              </label>
              <p className="muted">
                Get a key from your provider’s official developer dashboard,
                create a project/key, and set a spending limit if available.
                Paste it here, not into chat or source files. Saved keys are
                protected by Windows.
              </p>
            </div>
          )}
        </section>
        <section className="panel">
          <h2>Retrieval & uploads</h2>
          <label className="check">
            <input
              type="checkbox"
              checked={draft.embeddings_enabled}
              onChange={(e) =>
                setDraft({ ...draft, embeddings_enabled: e.target.checked })
              }
            />
            Combine local embeddings with BM25 keyword search
          </label>
          <label>
            Local embedding model
            <input
              value={draft.embedding_model}
              onChange={(e) =>
                setDraft({ ...draft, embedding_model: e.target.value })
              }
              required
            />
          </label>
          <p className="muted">
            Embeddings are cached in your library. If the model is unavailable,
            LitLens shows a keyword-only fallback.
          </p>
          <label className="check">
            <input
              type="checkbox"
              checked={draft.auto_analyze}
              onChange={(e) =>
                setDraft({ ...draft, auto_analyze: e.target.checked })
              }
            />
            Automatically analyze each uploaded PDF
          </label>
        </section>
        <section className="panel">
          <h2>OpenAlex discovery</h2>
          <label>
            OpenAlex API key
            <input
              type="password"
              autoComplete="off"
              placeholder={
                draft.has_openalex_api_key
                  ? "Saved securely · leave blank to keep"
                  : "Optional key for your OpenAlex account"
              }
              value={openalexKey}
              onChange={(e) => setOpenalexKey(e.target.value)}
            />
          </label>
          {draft.has_openalex_api_key && (
            <label className="check">
              <input
                type="checkbox"
                checked={clearOpenalex}
                onChange={(e) => setClearOpenalex(e.target.checked)}
              />
              Remove OpenAlex key
            </label>
          )}
          <p className="muted small">
            Basic searches work without a key. An OpenAlex key increases your
            request allowance. It is separate from your AI provider key.{" "}
            <a
              href="https://help.openalex.org/api/authentication/"
              target="_blank"
              rel="noreferrer"
            >
              Get an OpenAlex key ↗
            </a>
          </p>
        </section>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="success" role="status">
            {message}
          </p>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "Saving…" : "Save preferences"}
        </button>
      </form>
      <section className="panel setup-guide">
        <div className="row">
          <h2>Set up free local AI</h2>
          <button className="secondary" onClick={() => void refresh()}>
            Refresh models
          </button>
        </div>
        <p>
          <a
            href="https://ollama.com/download/windows"
            target="_blank"
            rel="noreferrer"
          >
            Install Ollama for Windows ↗
          </a>
          , then run these commands in PowerShell:
        </p>
        <pre>
          {[
            ...(settings.provider === "ollama" ? [settings.ollama_model] : []),
            ...(settings.embeddings_enabled ? [settings.embedding_model] : []),
          ]
            .map((model) => `ollama pull ${model}`)
            .join("\n") ||
            "No local models required for the saved preferences."}
        </pre>
        <p className={models?.ready ? "success" : "muted"}>
          {models?.available
            ? `Ollama connected · ${models.models.length} installed model(s)`
            : (models?.message ?? "Checking Ollama…")}
        </p>
        {models && (
          <ul className="model-readiness">
            {settings.provider === "ollama" && (
              <li>
                Chat · {settings.ollama_model}:{" "}
                <strong>
                  {installed(settings.ollama_model)
                    ? "Installed"
                    : "Not available"}
                </strong>
              </li>
            )}
            {settings.embeddings_enabled && (
              <li>
                Embeddings · {settings.embedding_model}:{" "}
                <strong>
                  {installed(settings.embedding_model)
                    ? "Installed"
                    : "Not available"}
                </strong>
              </li>
            )}
            {!models.ready && (
              <li className="error">
                Missing models: {models.missing_models.join(", ")}. Download
                them, then refresh.
              </li>
            )}
          </ul>
        )}
        <div className="chips">
          {models?.models.map((m) => (
            <span key={m.name} className="chip">
              {m.name}
            </span>
          ))}
        </div>
        <datalist id="ollama-models">
          {models?.models.map((m) => (
            <option key={m.name} value={m.name} />
          ))}
        </datalist>
        <p className="muted">
          The 3B model is a starting point for your 16 GB computer. Larger
          models may produce better explanations but need more memory and time.
          Model choice does not guarantee correctness.
        </p>
      </section>
      <BackupPanel onRestore={onRestore} />
    </div>
  );
}
