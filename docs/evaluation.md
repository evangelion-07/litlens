# Retrieval evaluation

The checked-in `data/evaluation/demo_corpus.json` is a three-question synthetic fixture. It verifies that the evaluation code runs; it is not a measure of LitLens accuracy on research papers.

## Real-paper benchmark protocol

Build a separate dataset from papers whose licenses permit local evaluation. Split each paper into its own chunks, retain page and paper provenance, then have a reviewer label questions with the exact relevant chunk IDs. Include answerable questions and unanswerable questions. Two reviewers should independently label at least a sample and resolve disagreements before using the labels as a quality result.

The benchmark should compare BM25, embedding-only ranking, and hybrid ranking on the same fixed papers and queries. Record model names, embedding endpoint, corpus revision, questions, relevant IDs, cutoff, and timestamp. Report Precision@k, Recall@k, MRR, and unanswerable abstention separately. Do not count synthetic or unreviewed examples as human-verified accuracy.

## Current tooling and status

Run `python evaluate.py` from `backend/` for the synthetic smoke fixture. It reports keyword retrieval and only reports hybrid results when a compatible embedding provider is configured. The current fixture contains no human labels and must not be used to claim real-paper quality.

The application now checks that requested evidence quotes appear verbatim in the cited source and that claim numbers appear in the quoted passages. This catches unsupported citations and invented numerical values. It does not prove semantic entailment; reviewers must still assess whether each passage actually supports the claim.

No real-paper benchmark is currently recorded. A permitted corpus and reviewer-checked questions are needed to produce defensible real-paper metrics. Benchmark authors must not invent relevance judgments to fill a target sample size.
