from api_support import authenticate_test
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from httpx import ASGITransport, AsyncClient

from app.main import app


class PaperSearchApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )
        await authenticate_test(self)

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_rejects_short_and_blank_queries(self):
        response = await self.client.get("/papers/search", params={"q": "x"})
        self.assertEqual(response.status_code, 422)
        response = await self.client.get("/papers/search", params={"q": "   "})
        self.assertEqual(response.status_code, 422)

    async def test_rejects_invalid_page_size(self):
        response = await self.client.get("/papers/search", params={"q": "valid query", "per_page": 26})
        self.assertEqual(response.status_code, 422)

    async def test_returns_search_results(self):
        expected = [{"title": "Paper", "abstract": "Evidence."}]
        with patch("app.api.papers.search_papers", new=AsyncMock(return_value=expected)) as search:
            response = await self.client.get(
                "/papers/search",
                params={"q": "  plant disease detection  ", "per_page": 3},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "query": "plant disease detection",
            "count": 1,
            "results": expected,
        })
        search.assert_awaited_once_with(query="plant disease detection", per_page=3)

    async def test_maps_timeout_and_rate_limit(self):
        with patch("app.api.papers.search_papers", new=AsyncMock(side_effect=httpx.ReadTimeout("slow"))):
            response = await self.client.get("/papers/search", params={"q": "valid query"})
        self.assertEqual(response.status_code, 504)

        request = httpx.Request("GET", "https://api.openalex.org/works")
        rate_limit = httpx.HTTPStatusError(
            "rate limited",
            request=request,
            response=httpx.Response(429, request=request),
        )
        with patch("app.api.papers.search_papers", new=AsyncMock(side_effect=rate_limit)):
            response = await self.client.get("/papers/search", params={"q": "valid query"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
