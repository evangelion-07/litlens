# Feature status

LitLens is a Windows desktop research reader with per-computer local accounts and local SQLite storage. It does not provide online account sync. Ollama is optional and runs on the user's computer; external AI is opt-in and requires explicit consent.

## Implemented

- Local account registration, login, logout, password hashing, isolated research profiles, and Windows-protected API credentials.
- PDF upload, text extraction, page reader, reports, history, paper comparison, cited paper chat, and OpenAlex discovery.
- BM25 retrieval with optional local Ollama embeddings and hybrid ranking.
- Report and answer evidence checks: citations must resolve, quoted text must match its source, and numbers in claims must appear in their quoted evidence. These checks do not determine whether a quote logically entails a claim or whether an interpretation is scientifically correct.
- Ollama readiness checks separately report the selected chat model and embedding model. Disabled embedding retrieval does not block Ollama chat readiness.
- Optional OpenAlex API key saved with Windows DPAPI. It is sent to OpenAlex only.
- Portable research backup and restore for PDFs, paper records, reports, and conversations. Backups omit account passwords, sessions, API keys, and embedding cache. Restore adds copies to the signed-in local profile.
- Windows installer and portable build. Installer is not Authenticode signed unless a publisher certificate is configured.

## Limits and verification

- Hybrid retrieval depends on Ollama being available and the configured embedding model being installed. Keyword retrieval remains available when embeddings cannot run.
- A machine-bound Windows credential cannot be transferred inside a backup. Each computer has its own local accounts and API-key settings.
- PDF extraction depends on readable text. Figures and complex tables may not be interpreted, and OCR requires separate setup.
- No human-reviewed real-paper benchmark is bundled. Metrics from the synthetic fixture are software checks only and must not be presented as research accuracy.
- No signing certificate is included with the project. A trusted public installer needs a code-signing certificate and a signing step in the release environment.
