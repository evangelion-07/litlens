# LitLens desktop migration

User-approved scope: Windows desktop application; local accounts; isolated user data;
automatic upload analysis; BM25 plus persisted local embeddings; Ollama and optional
API model settings; evidence-grounded Q&A; redesigned interface; regression tests.
Machine: 16 GB RAM, NVIDIA RTX 3050. Never promise scientific accuracy without evaluation.

Implementation in progress. Preserve the original data directory. Do not delete user PDFs.

## Work remaining
- Local authentication, user directories, encrypted provider settings.
- Ollama chat/embeddings, cache, explicit Q&A provider choice, answer support checks.
- Automatic analysis/indexing, comparison and deletion fixes.
- Desktop shell, packaging, redesigned authenticated UI.
- Regression tests, build, desktop smoke test, setup documentation.
- Completed: Windows build environment, account isolation, local Ollama and API settings,
  persistent embedding cache, automatic report and retrieval pipeline, repaired Q&A,
  comparison continuity, metadata deletion, desktop shell and redesigned UI.
- Completed: 65 backend tests, frontend type/build, installer build and Electron smoke
  test covering account creation, settings, upload, analysis, cited evidence, chat,
  chat persistence, and paper deletion. npm audit reports zero vulnerabilities.
- Machine's 16 GB RAM and RTX 3050 were confirmed. Chosen starter models: qwen2.5:3b
  and nomic-embed-text. Ollama is not currently confirmed installed; install and pull
  these models before enabling live local inference.
- Remaining: package current installer, run packaged-installer smoke test, consider
  export/import of the legacy database after verifying the migration boundary, and
  run accuracy evaluation against a real annotated corpus.

No API key is needed for local Ollama. Keys should be entered in the application's settings,
not shared in chat. Check this file and git status when resuming after a session limit.

## Follow-up design changes (2026-11-15)
- Luxury glass-style login/signup, reduced copy, animated LitLens mark, and persistent light/dark theme.
- Primary navigation now includes paper reader and paper assistant. Uploaded PDFs open in an embedded reader; OpenAlex entries show available abstract/metadata and safe external publication links.
- Paper Q&A remains limited to the selected paper and retrieves evidence before Ollama answers.
- Removed self-hosted backend selection and remote sync support at user request. LitLens is local-only again.
- First-run Ollama setup offers the official installer link and model pull commands. Model weights stay outside the single-executable LitLens installer.
- Built frontend and NSIS installer after the UI changes. Installer output is under `release/`.
