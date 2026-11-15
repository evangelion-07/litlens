import unittest

import pymupdf

from app.services.report_export import report_markdown, report_pdf


REPORT = {
    "title": "Evidence First Study",
    "generated_at": "2026-10-25T00:00:00+00:00",
    "analysis_mode": "local_extractive",
    "coverage": {
        "scope": "full_text",
        "pages_analyzed": 1,
        "total_pages": 1,
        "analyzed_units": 1,
        "note": "One page of selectable text.",
    },
    "executive_summary": {"text": "A concise finding.", "evidence_ids": ["E1"]},
    "section_summaries": {},
    "key_findings": [],
    "strengths": [],
    "weaknesses": [],
    "recommendations": [],
    "research_gaps": [],
    "priority_action_plan": [],
    "evidence": [{
        "evidence_id": "E1",
        "paper_title": "Evidence First Study",
        "section": "Results",
        "page_number": 1,
        "excerpt": "The result is supported by the paper.",
    }],
    "caveats": ["Citation presence does not prove entailment."],
}


class ReportExportTests(unittest.TestCase):
    def test_markdown_export_keeps_evidence_references(self):
        output = report_markdown(REPORT)
        self.assertIn("A concise finding. [E1]", output)
        self.assertIn("[E1] Evidence First Study", output)
        self.assertIn("page 1", output)

    def test_pdf_export_is_readable_and_keeps_cited_text(self):
        output = report_pdf(REPORT)
        self.assertTrue(output.startswith(b"%PDF"))
        document = pymupdf.open(stream=output, filetype="pdf")
        text = "\n".join(page.get_text() for page in document)
        document.close()
        self.assertIn("Evidence First Study", text)
        self.assertIn("[E1]", text)


if __name__ == "__main__":
    unittest.main()
