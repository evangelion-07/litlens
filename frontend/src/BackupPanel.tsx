import { useRef, useState } from "react";
import { api, download } from "./api";

export function BackupPanel({ onRestore }: { onRestore: () => Promise<void> }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function exportBackup() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await download(
        "/backups/export",
        `LitLens-backup-${new Date().toISOString().slice(0, 10)}.zip`,
      );
      setMessage("Backup download started. Keep it in a safe location.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    if (!file) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (file.size > 512 * 1024 * 1024)
        throw new Error("Choose a backup smaller than 512 MB.");
      const result = await api<{
        papers_restored: number;
        reports_restored: number;
      }>("/backups/restore", {
        method: "POST",
        headers: { "Content-Type": "application/zip" },
        body: file,
      });
      await onRestore();
      setFile(null);
      if (input.current) input.current.value = "";
      setMessage(
        `Restored ${result.papers_restored} paper(s) and ${result.reports_restored} report(s).`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel backup-panel">
      <h2>Back up & restore research</h2>
      <p>
        Keep a copy of your PDFs, reports, and paper conversations, or move them
        to another PC.
      </p>
      <p className="muted small">
        Backups exclude passwords, API keys, and model settings. Sign in to a
        local account on the new PC before restoring. The ZIP contains readable
        research data; keep it private.
      </p>
      <div className="row">
        <button
          className="secondary"
          disabled={busy}
          onClick={() => void exportBackup()}
        >
          Export research backup
        </button>
        <button
          className="secondary"
          disabled={busy}
          onClick={() => input.current?.click()}
        >
          Choose backup to restore
        </button>
      </div>
      <input
        ref={input}
        type="file"
        accept=".zip,application/zip"
        aria-label="Research backup file"
        hidden
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          setError("");
          setMessage("");
        }}
      />
      {file && (
        <div className="insight">
          <p>
            <strong>{file.name}</strong>
          </p>
          <p>
            Restore adds copies to this account. Existing papers are kept.
            Importing the same backup again creates duplicates.
          </p>
          <button
            className="primary"
            disabled={busy}
            onClick={() => void restore()}
          >
            {busy ? "Restoring…" : "Restore into this account"}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="success">
          {message}
        </p>
      )}
    </section>
  );
}
