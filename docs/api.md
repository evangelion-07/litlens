# API notes

The OpenAPI page is available at http://localhost:8000/docs while the backend is running.

| Method and path | Purpose |
| --- | --- |
| GET / | API welcome response |
| GET /health | Health status |
| GET /analysis/capabilities | Reports LLM configuration, OCR availability, Crossref availability, and upload limit |
| GET /papers/search?q=...&per_page=10 | Search OpenAlex; q must contain 2–200 non-space characters and per_page must be 1–25 |
| GET /papers/crossref/verify?doi=... | Verify and return Crossref metadata for one DOI |
| GET /library/papers | List stored metadata records and uploaded PDFs |
| POST /library/papers | Save or merge an OpenAlex metadata record |
| POST /library/upload?filename=paper.pdf | Upload PDF bytes with Content-Type: application/pdf |
| GET /library/papers/{paper_id} | Read one library record |
| GET /library/papers/{paper_id}/pages | Read extracted page text and provenance |
| DELETE /library/papers/{paper_id} | Remove a stored paper and its uploaded PDF |
| POST /library/compare | Compare 2–5 distinct saved papers |
| POST /assistant/ask | Retrieve evidence and answer, or abstain |
| POST /analysis/papers/{paper_id} | Start a persistent analysis job; body: {"use_external_ai": false} |
| GET /analysis/papers/{paper_id}/latest | Read the latest analysis for a paper |
| GET /analysis/history?limit=50 | List analysis jobs without report bodies |
| GET /analysis/{analysis_id} | Read job status and its report when complete |
| GET /analysis/{analysis_id}/export?format=markdown or pdf | Download a completed report with citations |

## Analysis job

POST /analysis/papers/{paper_id} returns HTTP 202 and an analysis ID, status, stage, and progress. Poll GET /analysis/{analysis_id} until status is completed or failed. The report labels coverage as full_text, partial_text, abstract_only, or no_text and includes page-aware evidence IDs. A metadata-only paper with no abstract produces an explicit no-text report.

Set use_external_ai to true only when the user has configured and opted in to a language-model provider. If no provider is configured, the request returns 422. Extracted text is sent to the external provider only for that opted-in job. Provider failure falls back to a local extractive report with a caveat.

## Question answering

POST /assistant/ask accepts a JSON body such as {"question":"What method was used?","paper_ids":["paper-id"],"top_k":5,"conversation":[{"role":"user","content":"What problem does the paper address?"}]}. The conversation field is optional and accepts up to 12 recent user/assistant turns. It is context for interpreting follow-ups; only newly retrieved passages are used as evidence. An empty paper_ids list searches the full library.

The response includes answer, answer_mode, retrieval_mode, sufficient_evidence, message, evidence, and citations. Each citation identifies the evidence marker, paper ID/title, chunk ID, PDF page when available, and a short source excerpt. Citation validation checks that markers refer to evidence retrieved for the current answer; it does not prove logical entailment.

## Upload and comparison

The upload limit defaults to 20 MB and can be changed with LITLENS_MAX_UPLOAD_MB. Upload validates the PDF signature, filename, and content type. It stores page text separately, keeps chunks page-local, attempts detectable table extraction, and tries OCR only when Tesseract is available and OCR is enabled. An image-only PDF may therefore remain no_text.

Comparison returns per-paper sections only when explicit headings were recognized. The UI marks missing values as not reported or not detected in available text. Potential gaps are scoped to the selected papers and must not be treated as global novelty claims.

## Errors

- Invalid query or request body: 422.
- Wrong PDF type: 415; oversized PDF: 413; invalid or encrypted PDF: 422.
- OpenAlex timeout: 504; upstream rate limiting: 503; other unsuccessful or malformed response: 502.
- Crossref DOI not found: 404; Crossref unavailable or rate limited: 503; malformed response: 502.
- Missing paper or analysis: 404; analysis still running at export time: 409.
- Provider-assisted analysis without configured LLM_API_URL and LLM_MODEL: 422.
