# LitLens Desktop

LitLens is a Windows desktop research workspace. By default it stores local accounts, papers, extracted PDF text, cached embeddings, conversations, and reports on this computer. Each account has an isolated library. PDFs can be imported whether or not they appear in OpenAlex.

## Run the development version

Install Node.js, Ollama, and Python 3.12. Then, from PowerShell in this folder:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
npm install
npm run start
```

`npm run start` builds the React interface and opens LitLens in Electron. Create a local account on first use. Accounts, papers, reports, preferences, and chat history are stored on this computer and do not sync across devices. Back up `%APPDATA%\litlens-desktop\data` if the application is packaged. In the development version, the default database is in the project `data` directory.

## Share LitLens with another Windows user

Build the self-contained desktop folder with `npm run build:portable`. The resulting files are in `release\win-unpacked`; zip that folder to share one download. After extracting the zip, open `LitLens.exe`. No project source, Node.js, or Python installation is needed. Each person creates their own local account and keeps their own library on their PC. For AI features, install Ollama on that PC and follow the first-run model setup shown by LitLens. Ollama and its model files are downloaded separately and are not part of the app archive.

## Local models (free, no API key)

Install [Ollama for Windows](https://ollama.com/download/windows), start it, and run:

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Open **Models & preferences** in LitLens, refresh the model list, and select the installed chat model. `nomic-embed-text` is configured as the embedding model. LitLens combines its locally generated embeddings with BM25 keyword retrieval. Cached embeddings are isolated per account and embedding model. Ollama's chat and embedding endpoints run on localhost; paper text stays local when using these local models. See [Ollama Windows](https://docs.ollama.com/windows), [Ollama chat API](https://docs.ollama.com/api/chat), and [Ollama embedding API](https://docs.ollama.com/api/embed).

## Optional hosted API

No hosted API key is required to use Ollama. To use an OpenAI-compatible provider, open **Models & preferences**, choose **API provider**, enter the provider's HTTPS chat-completions endpoint and model ID, paste the key into the password field, and explicitly consent to sending passages to that provider. On Windows, LitLens protects the saved key with the current Windows account's DPAPI. Keys are never returned by the settings API. To obtain a key, use the provider's official developer console, create a project/API key, configure a spending limit if available, and paste it directly into LitLens. Never put a real key in source code or chat.

## What analysis does

PDF upload extracts page text, preserves page numbers, recognizes a limited set of headings, and can automatically run local BM25 plus embeddings to select passages about methods, data, evaluation, limitations, and future work. When Ollama or a consented API is selected, the LLM receives those selected passages to prepare a structured report. Citations must refer to real evidence IDs; unknown IDs are rejected. If the model is unavailable, local extractive analysis still completes and the report records the fallback. Questions retrieve passages again and can optionally request an LLM answer. The answer checker requires an exact supporting quote for each generated claim and rejects unsupported numeric claims.

These checks reduce errors but cannot guarantee scientific correctness or entailment. PDF text extraction can miss unusual layouts, formulas, figures, and image-only pages. OCR requires a separate Tesseract installation. Review every conclusion and its cited passage. Research novelty still requires a wider literature review. The included evaluation fixture is synthetic and must not be reported as real-world accuracy.

## Development checks and Windows build

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd ..
npm run build:frontend
npm run test:desktop
npm audit
npm run build:desktop
```

The Windows installer is written to `release/` as a single setup `.exe`. It bundles LitLens and the local backend, not Ollama or model weights; first launch offers the official Ollama download and model setup commands. Install Ollama and download models once on this computer. A production release should be code-signed before broad distribution.

## Original project data

Existing files in `data/` were preserved. The initial legacy SQLite database is not automatically exposed inside the new per-account profiles. Import only records you want to keep through the signed-in library workflow. Local accounts are not cloud accounts and do not synchronize.
