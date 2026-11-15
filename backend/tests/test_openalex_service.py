import unittest

from app.services.openalex_service import (
    deduplicate_papers,
    normalize_doi,
    parse_openalex_work,
    reconstruct_abstract,
)


class AbstractReconstructionTests(unittest.TestCase):
    def test_reconstructs_tokens_in_position_order(self):
        index = {
            "retrieval": [3],
            "evidence": [0],
            "grounded": [2],
            "answers": [1],
        }
        self.assertEqual(
            reconstruct_abstract(index),
            "evidence answers grounded retrieval",
        )

    def test_repeated_token_is_placed_at_each_position(self):
        self.assertEqual(
            reconstruct_abstract({"paper": [0, 2], "research": [1]}),
            "paper research paper",
        )

    def test_missing_or_empty_abstract_returns_none(self):
        self.assertIsNone(reconstruct_abstract(None))
        self.assertIsNone(reconstruct_abstract({}))
        self.assertIsNone(reconstruct_abstract({"word": []}))

    def test_ignores_invalid_positions_and_malformed_entries(self):
        self.assertEqual(
            reconstruct_abstract({
                "valid": [1],
                "bad": [-1, True, "0", None],
                "": [0],
                "not a sequence": "0",
            }),
            "valid",
        )


class OpenAlexNormalizationTests(unittest.TestCase):
    def test_normalizes_resolver_urls_and_doi_prefix(self):
        self.assertEqual(normalize_doi(" HTTPS://DOI.ORG/10.5555/AbC "), "10.5555/abc")
        self.assertEqual(normalize_doi("doi: 10.5555/DEF"), "10.5555/def")
        self.assertIsNone(normalize_doi(None))
        self.assertIsNone(normalize_doi("  "))

    def test_parses_abstract_and_missing_fields(self):
        paper = parse_openalex_work({
            "id": "https://openalex.org/W1",
            "display_name": "Example paper",
            "doi": "https://doi.org/10.5555/ABC",
            "abstract_inverted_index": {"Evidence": [0], "matters.": [1]},
            "authorships": [{"author": {"display_name": "A. Researcher"}}],
            "open_access": {"is_oa": True},
            "primary_location": {"pdf_url": "https://example.org/paper.pdf"},
        })
        self.assertEqual(paper["title"], "Example paper")
        self.assertEqual(paper["doi"], "10.5555/abc")
        self.assertEqual(paper["abstract"], "Evidence matters.")
        self.assertEqual(paper["authors"], ["A. Researcher"])
        self.assertTrue(paper["open_access"])
        self.assertEqual(paper["landing_page_url"], None)
        self.assertEqual(paper["pdf_url"], "https://example.org/paper.pdf")

    def test_deduplicates_normalized_doi_and_merges_missing_fields(self):
        papers = deduplicate_papers([
            {"openalex_id": "W1", "doi": "https://doi.org/10.5555/ABC", "abstract": None, "open_access": False},
            {"openalex_id": "W2", "doi": "10.5555/abc", "abstract": "Recovered text", "open_access": True},
            {"openalex_id": "W3", "doi": None, "title": "Distinct work"},
        ])
        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0]["doi"], "10.5555/abc")
        self.assertEqual(papers[0]["abstract"], "Recovered text")
        self.assertTrue(papers[0]["open_access"])


if __name__ == "__main__":
    unittest.main()
