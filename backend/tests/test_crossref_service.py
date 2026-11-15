import unittest
from unittest.mock import patch

import httpx

from app.services.crossref_service import verify_crossref_doi


class CrossrefVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalizes_and_verifies_a_doi_record(self):
        async def handler(request):
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1000/example.1",
                        "title": ["Verified title"],
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "published-print": {"date-parts": [[2024, 3, 1]]},
                        "type": "journal-article",
                        "publisher": "Example Press",
                        "container-title": ["Journal of Examples"],
                        "URL": "https://doi.org/10.1000/example.1",
                        "abstract": "<jats:p>Verified abstract.</jats:p>",
                    }
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        original_client = httpx.AsyncClient
        def client_factory(*args, **kwargs):
            return original_client(transport=transport, **kwargs)

        with patch("app.services.crossref_service.httpx.AsyncClient", client_factory):
            result = await verify_crossref_doi("https://doi.org/10.1000/example.1")

        self.assertTrue(result["verified"])
        self.assertEqual(result["doi"], "10.1000/example.1")
        self.assertEqual(result["title"], "Verified title")
        self.assertEqual(result["authors"], ["Ada Lovelace"])
        self.assertEqual(result["publication_year"], 2024)
        self.assertEqual(result["publisher"], "Example Press")

    async def test_rejects_an_invalid_doi_before_network_access(self):
        with self.assertRaises(ValueError):
            await verify_crossref_doi("not-a-doi")


if __name__ == "__main__":
    unittest.main()
