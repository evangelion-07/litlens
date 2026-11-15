import unittest

from app.services.comparison_service import compare_papers, extract_sections


class SectionExtractionTests(unittest.TestCase):
    def test_extracts_explicit_sections_with_page_numbers(self):
        sections = extract_sections([
            {
                "page_number": 2,
                "text": "Methods\nWe used a convolutional model.\nDataset\nPlantVillage images.\nResults\nAccuracy was 91 percent.\nLimitations\nThe field sample is small.",
            },
            {"page_number": 3, "text": "Future Work\nEvaluate new field images."},
        ])
        self.assertEqual(sections["methods"]["page_numbers"], [2])
        self.assertIn("convolutional model", sections["methods"]["text"])
        self.assertEqual(sections["datasets"]["page_numbers"], [2])
        self.assertEqual(sections["findings"]["page_numbers"], [2])
        self.assertEqual(sections["limitations"]["page_numbers"], [2])
        self.assertEqual(sections["future_work"]["page_numbers"], [3])

    def test_detects_all_requested_comparison_dimensions_when_explicitly_headed(self):
        sections = extract_sections([{
            "page_number": 8,
            "text": (
                "Experimental Design\nTwo evaluation cohorts.\n"
                "Baselines\nA support-vector classifier.\n"
                "Evaluation Metrics\nMacro F1 and recall.\n"
                "Strengths\nThe method is computationally small.\n"
                "Research Gaps\nExternal validation is needed."
            ),
        }])
        self.assertEqual(sections["experimental_design"]["page_numbers"], [8])
        self.assertIn("support-vector classifier", sections["baselines"]["text"])
        self.assertIn("Macro F1", sections["evaluation_metrics"]["text"])
        self.assertIn("computationally small", sections["strengths"]["text"])
        self.assertIn("External validation", sections["research_gaps"]["text"])

    def test_unlabeled_text_is_not_guessed_as_a_method(self):
        sections = extract_sections([
            {"page_number": 1, "text": "We used several algorithms and a public dataset."}
        ])
        self.assertNotIn("methods", sections)
        self.assertNotIn("datasets", sections)

    def test_abstract_is_used_only_as_objective_fallback(self):
        sections = extract_sections([], abstract="This paper studies crop classification.")
        self.assertEqual(sections["objective"]["source_kind"], "abstract")
        self.assertEqual(sections["objective"]["page_numbers"], [])
        self.assertNotIn("methods", sections)


class ComparisonAnalysisTests(unittest.TestCase):
    def test_comparison_keeps_limitations_as_scoped_low_confidence_hypotheses(self):
        result = compare_papers([
            {
                "paper": {
                    "id": "p1", "title": "Paper one", "publication_year": 2024,
                    "authors": ["A. Author"], "source_type": "upload", "abstract": None,
                },
                "pages": [{"page_number": 4, "text": "Limitations\nThe study uses a small field sample.\nFuture Work\nEvaluate across regions."}],
            },
            {
                "paper": {
                    "id": "p2", "title": "Paper two", "publication_year": 2025,
                    "authors": ["A. Author"], "source_type": "upload", "abstract": None,
                },
                "pages": [{"page_number": 7, "text": "Methods\nWe test another classifier."}],
            },
        ])
        self.assertEqual(result["shared_authors"], ["A. Author"])
        self.assertEqual(result["publication_year_range"], [2024, 2025])
        self.assertEqual(result["reported_limitations"][0]["page_numbers"], [4])
        self.assertEqual(result["potential_gaps"][0]["confidence"], "low")
        self.assertEqual(result["potential_gaps"][0]["supporting_paper_id"], "p1")
        self.assertIn("does not establish global novelty", result["potential_gaps"][0]["scope_note"])


if __name__ == "__main__":
    unittest.main()
