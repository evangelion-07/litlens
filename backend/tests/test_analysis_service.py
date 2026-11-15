import unittest

from app.services.analysis_service import _batches, analyze_paper


class PaperAnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def test_abstract_only_paper_is_labeled_and_cited(self):
        paper = {
            "id": "paper-abstract",
            "title": "A Study Based on an Abstract",
            "authors": ["A. Researcher"],
            "publication_year": 2025,
            "doi": None,
            "abstract": "This study evaluates a retrieval method on a curated collection.",
            "page_count": 0,
        }
        report = await analyze_paper("analysis-1", paper, [], [])

        self.assertEqual(report.coverage.scope, "abstract_only")
        self.assertIn("Abstract", report.coverage.identified_sections)
        self.assertEqual(report.section_summaries["abstract"].status, "found")
        self.assertEqual(report.section_summaries["abstract"].evidence_ids, ["E1"])
        self.assertEqual(report.evidence[0].source_kind, "abstract")
        self.assertIsNone(report.evidence[0].page_number)
        self.assertIn("Abstract-only", report.executive_summary.text)

    async def test_no_text_report_does_not_invent_findings_or_evidence(self):
        paper = {
            "id": "paper-empty",
            "title": "Scanned Paper",
            "authors": [],
            "publication_year": None,
            "doi": None,
            "abstract": None,
            "page_count": 2,
        }
        report = await analyze_paper(
            "analysis-2",
            paper,
            [{"page_number": 1, "text": ""}, {"page_number": 2, "text": ""}],
            [],
        )

        self.assertEqual(report.coverage.scope, "no_text")
        self.assertEqual(report.key_findings, [])
        self.assertEqual(report.evidence, [])
        self.assertIn("No paper text", report.executive_summary.text)


class LongDocumentBatchTests(unittest.TestCase):
    def test_every_chunk_is_kept_in_bounded_batches(self):
        units = [
            {"evidence_id": "E1", "text": "A" * 4500},
            {"evidence_id": "E2", "text": "B" * 4500},
            {"evidence_id": "E3", "text": "C" * 4500},
        ]
        batches = _batches(units)
        self.assertGreater(len(batches), 1)
        self.assertEqual(
            [item["evidence_id"] for batch in batches for item in batch],
            ["E1", "E2", "E3"],
        )


if __name__ == "__main__":
    unittest.main()
