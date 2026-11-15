import unittest
import json

from app.services.assistant_service import answer_question, validate_citations


DOCUMENTS = [{
    "chunk_id": "chunk-1",
    "paper_id": "paper-1",
    "title": "Classification study",
    "page_number": 3,
    "ordinal": 0,
    "source_kind": "pdf",
    "text": "The study uses logistic regression as its classification method and reports its limitations.",
}]


class StubLLM:
    def __init__(self, answer):
        self.answer = answer
        self.system_prompt = None
        self.user_prompt = None

    async def complete(self, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.answer


class CitationValidationTests(unittest.TestCase):
    def test_accepts_only_citations_in_retrieved_evidence(self):
        evidence = [{"evidence_id": "E1", "chunk_id": "chunk-1"}]
        self.assertEqual(validate_citations("Supported claim [E1].", evidence)[0], True)
        self.assertEqual(validate_citations("Unsupported claim [E2].", evidence)[0], False)
        self.assertEqual(validate_citations("No citation.", evidence)[0], False)


class EvidenceGroundedAnswerTests(unittest.IsolatedAsyncioTestCase):
    async def test_abstains_when_no_documents_are_available(self):
        response = await answer_question("What method was used?", [])
        self.assertEqual(response["answer_mode"], "abstain")
        self.assertFalse(response["sufficient_evidence"])
        self.assertEqual(response["citations"], [])

    async def test_extractive_fallback_cites_the_source_page(self):
        response = await answer_question("What classification method was used?", DOCUMENTS)
        self.assertEqual(response["answer_mode"], "extractive")
        self.assertIn("[E1]", response["answer"])
        self.assertEqual(response["citations"][0]["paper_id"], "paper-1")
        self.assertEqual(response["citations"][0]["page_number"], 3)
        self.assertEqual(response["citations"][0]["chunk_id"], "chunk-1")

    async def test_unverified_model_citations_are_replaced_by_evidence_quotes(self):
        response = await answer_question(
            "What classification method was used?",
            DOCUMENTS,
            llm_provider=StubLLM("The paper used a transformer [E99]."),
        )
        self.assertEqual(response["answer_mode"], "extractive")
        self.assertIn("[E1]", response["answer"])
        self.assertNotIn("E99", response["answer"])

    async def test_valid_model_citation_is_returned(self):
        response = await answer_question(
            "What classification method was used?",
            DOCUMENTS,
            llm_provider=StubLLM(json.dumps({"answerable": True, "claims": [{"text": "The study used logistic regression.", "evidence_id": "E1", "quote": "The study uses logistic regression"}]})),
        )
        self.assertEqual(response["answer_mode"], "llm")
        self.assertEqual(response["citations"][0]["evidence_id"], "E1")


    async def test_follow_up_context_is_used_but_citations_still_come_from_retrieved_evidence(self):
        provider = StubLLM("The paper reports logistic regression [E1].")
        response = await answer_question(
            "And what about its limitations?",
            DOCUMENTS,
            llm_provider=provider,
            conversation=[
                {"role": "user", "content": "What classification method did the paper use?"},
                {"role": "assistant", "content": "The prior answer referenced the method."},
            ],
        )
        self.assertIn("classification method", provider.user_prompt.casefold())
        self.assertIn("And what about its limitations?", provider.user_prompt)
        self.assertIn("context only", provider.user_prompt.casefold())
        self.assertEqual(response["citations"][0]["evidence_id"], "E1")


if __name__ == "__main__":
    unittest.main()
