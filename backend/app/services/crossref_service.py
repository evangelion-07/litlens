from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.services.openalex_service import normalize_doi

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


class CrossrefNotFound(LookupError):
    pass


class CrossrefUnavailable(RuntimeError):
    pass


class CrossrefMetadataError(RuntimeError):
    pass


def _year(message: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (message.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and isinstance(parts[0][0], int):
            return parts[0][0]
    return None


async def verify_crossref_doi(doi: str) -> dict[str, Any]:
    normalized = normalize_doi(doi)
    if not normalized or len(normalized) > 255 or not _DOI_RE.fullmatch(normalized):
        raise ValueError("Enter a valid DOI such as 10.1000/example.123.")

    mailto = os.getenv("CROSSREF_MAILTO", "").strip()
    params = {"mailto": mailto} if mailto else None
    url = "https://api.crossref.org/works/" + quote(normalized, safe="")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=4.0)) as client:
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": "LitLens/0.3 (metadata verification)"},
            )
    except httpx.TimeoutException as exc:
        raise CrossrefUnavailable("Crossref timed out; try again shortly.") from exc
    except httpx.RequestError as exc:
        raise CrossrefUnavailable("Could not connect to Crossref; check your network.") from exc

    if response.status_code == 404:
        raise CrossrefNotFound("Crossref has no metadata record for this DOI.")
    if response.status_code >= 500 or response.status_code == 429:
        raise CrossrefUnavailable("Crossref is temporarily unavailable or rate limiting requests.")
    if not response.is_success:
        raise CrossrefMetadataError("Crossref rejected the DOI lookup.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise CrossrefMetadataError("Crossref returned invalid JSON.") from exc

    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict):
        raise CrossrefMetadataError("Crossref returned an invalid metadata record.")
    returned_doi = normalize_doi(message.get("DOI"))
    if returned_doi != normalized:
        raise CrossrefMetadataError("Crossref returned metadata for a different DOI.")

    authors = []
    for author in message.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = " ".join(part for part in (author.get("given"), author.get("family")) if part).strip()
        if name:
            authors.append(name)
    titles = message.get("title") or []
    containers = message.get("container-title") or []
    return {
        "source": "Crossref",
        "doi": returned_doi,
        "verified": True,
        "title": str(titles[0]) if titles else None,
        "authors": authors,
        "publication_year": _year(message),
        "publication_type": message.get("type"),
        "publisher": message.get("publisher"),
        "container_title": str(containers[0]) if containers else None,
        "url": message.get("URL"),
        "abstract": str(message.get("abstract") or "").strip() or None,
    }