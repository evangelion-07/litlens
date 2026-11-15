from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.services.embedding_provider import configured_embedding_provider
from app.services.evaluation import evaluate_hybrid, evaluate_keyword


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "data" / "evaluation" / "demo_corpus.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    queries = dataset["queries"]
    documents = dataset["documents"]
    report = {
        "dataset": dataset["name"],
        "dataset_note": dataset["note"],
        "keyword": evaluate_keyword(queries, documents, k=3),
    }
    provider = configured_embedding_provider()
    if provider is None:
        report["hybrid"] = {
            "status": "not_run",
            "reason": "Set EMBEDDING_API_URL and EMBEDDING_MODEL to measure semantic/hybrid retrieval.",
        }
    else:
        report["hybrid"] = {
            "status": "measured",
            **asyncio.run(evaluate_hybrid(queries, documents, provider, k=3)),
        }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
