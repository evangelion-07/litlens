import json
import unittest
from pathlib import Path

from app.services.evaluation import evaluate_keyword, evaluate_rankings


class RetrievalMetricsTests(unittest.TestCase):
    def test_metrics_use_expected_relevant_ids(self):
        queries = [
            {"id": "q1", "relevant_chunk_ids": ["a"]},
            {"id": "q2", "relevant_chunk_ids": ["c"]},
        ]
        result = evaluate_rankings(queries, {"q1": ["a", "b"], "q2": ["b", "c"]}, k=2)
        self.assertEqual(result["precision_at_k"], 0.5)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["mean_reciprocal_rank"], 0.75)

    def test_synthetic_corpus_runs_keyword_metrics(self):
        project_root = Path(__file__).resolve().parents[2]
        dataset = json.loads((project_root / "data" / "evaluation" / "demo_corpus.json").read_text(encoding="utf-8"))
        result = evaluate_keyword(dataset["queries"], dataset["documents"], k=3)
        self.assertEqual(result["query_count"], 3)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["mean_reciprocal_rank"], 1.0)


if __name__ == "__main__":
    unittest.main()
