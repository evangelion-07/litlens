import unittest

from app.services.retrieval_service import fuse_rankings, keyword_search, retrieve_evidence


DOCUMENTS = [
    {
        "chunk_id": "c1",
        "paper_id": "p1",
        "title": "Plant disease detection",
        "page_number": 2,
        "ordinal": 0,
        "text": "A convolutional neural network detects plant leaf disease from field images.",
    },
    {
        "chunk_id": "c2",
        "paper_id": "p2",
        "title": "Climate forecasting",
        "page_number": 4,
        "ordinal": 0,
        "text": "The model forecasts regional rainfall using a seasonal climate series.",
    },
]


class KeywordRetrievalTests(unittest.TestCase):
    def test_ranks_relevant_page_and_returns_provenance(self):
        results = keyword_search("plant disease detection", DOCUMENTS)
        self.assertEqual(results[0]["chunk_id"], "c1")
        self.assertEqual(results[0]["page_number"], 2)
        self.assertEqual(results[0]["retrieval_mode"], "keyword")

    def test_returns_no_evidence_for_unmatched_question(self):
        self.assertEqual(keyword_search("quantum cryptography", DOCUMENTS), [])

    def test_hybrid_rank_fusion_combines_both_lists(self):
        keywords = [{**DOCUMENTS[0], "score": 1.0}]
        semantic = [{**DOCUMENTS[1], "score": 0.9}, {**DOCUMENTS[0], "score": 0.8}]
        fused = fuse_rankings(keywords, semantic, 2)
        self.assertEqual({item["chunk_id"] for item in fused}, {"c1", "c2"})
        self.assertTrue(all(item["retrieval_mode"] == "hybrid" for item in fused))


class StubEmbeddingProvider:
    async def embed(self, texts):
        return [[1.0, 0.0], [0.2, 0.98], [0.9, 0.1]]


class HybridRetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_enables_hybrid_retrieval(self):
        evidence, mode, notice = await retrieve_evidence(
            "plant disease detection",
            DOCUMENTS,
            limit=2,
            embedding_provider=StubEmbeddingProvider(),
        )
        self.assertEqual(mode, "hybrid")
        self.assertIsNone(notice)
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0]["evidence_id"], "E1")

    async def test_provider_failure_falls_back_to_keyword(self):
        class FailingProvider:
            async def embed(self, texts):
                raise RuntimeError("offline")

        evidence, mode, notice = await retrieve_evidence(
            "plant disease detection",
            DOCUMENTS,
            embedding_provider=FailingProvider(),
        )
        self.assertEqual(mode, "keyword-fallback")
        self.assertIn("keyword retrieval", notice)
        self.assertEqual(evidence[0]["chunk_id"], "c1")


if __name__ == "__main__":
    unittest.main()
