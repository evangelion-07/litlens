from __future__ import annotations

import re
import os
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

OPENALEX_API_URL = "https://api.openalex.org/works"
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


class OpenAlexResponseError(RuntimeError):
    """Raised when OpenAlex returns data that cannot be parsed as a works response."""


def reconstruct_abstract(inverted_index: Any) -> str | None:
    """Rebuild an OpenAlex abstract from its token-to-position index."""
    if not isinstance(inverted_index, Mapping) or not inverted_index:
        return None

    positioned_tokens: dict[int, str] = {}
    for token, positions in inverted_index.items():
        if not isinstance(token, str) or not token.strip():
            continue
        if not isinstance(positions, Sequence) or isinstance(positions, (str, bytes)):
            continue

        for position in positions:
            if isinstance(position, bool) or not isinstance(position, int) or position < 0:
                continue
            positioned_tokens.setdefault(position, token)

    if not positioned_tokens:
        return None

    abstract = " ".join(positioned_tokens[position] for position in sorted(positioned_tokens))
    return abstract.strip() or None


def normalize_doi(value: Any) -> str | None:
    """Return a DOI identifier without resolver prefixes, in canonical lowercase."""
    if not isinstance(value, str):
        return None

    doi = value.strip().strip("<>").strip()
    doi = _DOI_PREFIX.sub("", doi, count=1).strip().strip("<>").strip().lower()
    return doi or None


def parse_openalex_work(work: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one OpenAlex work into the API's stable paper result shape."""
    authors: list[str] = []
    authorships = work.get("authorships")
    if isinstance(authorships, list):
        for authorship in authorships:
            if not isinstance(authorship, Mapping):
                continue
            author = authorship.get("author")
            if isinstance(author, Mapping):
                display_name = author.get("display_name")
                if isinstance(display_name, str) and display_name.strip():
                    authors.append(display_name.strip())

    primary_location = work.get("primary_location")
    if not isinstance(primary_location, Mapping):
        primary_location = {}
    open_access = work.get("open_access")
    if not isinstance(open_access, Mapping):
        open_access = {}

    title = work.get("title") or work.get("display_name")
    if isinstance(title, str):
        title = title.strip() or None
    else:
        title = None

    return {
        "openalex_id": work.get("id") if isinstance(work.get("id"), str) else None,
        "title": title,
        "authors": authors,
        "year": work.get("publication_year"),
        "doi": normalize_doi(work.get("doi")),
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "publication_type": work.get("type"),
        "cited_by_count": work.get("cited_by_count"),
        "open_access": open_access.get("is_oa") is True,
        "landing_page_url": primary_location.get("landing_page_url"),
        "pdf_url": primary_location.get("pdf_url"),
    }


def deduplicate_papers(papers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by normalized DOI, then OpenAlex ID, preserving result order."""
    results: list[dict[str, Any]] = []
    positions_by_key: dict[str, int] = {}

    for raw_paper in papers:
        paper = dict(raw_paper)
        doi = normalize_doi(paper.get("doi"))
        if doi:
            paper["doi"] = doi
            key = f"doi:{doi}"
        else:
            openalex_id = paper.get("openalex_id")
            if isinstance(openalex_id, str) and openalex_id.strip():
                key = f"openalex:{openalex_id.strip().casefold()}"
            else:
                title = paper.get("title")
                year = paper.get("year")
                authors = paper.get("authors") or []
                if not isinstance(title, str) or not title.strip():
                    key = f"anonymous:{len(results)}"
                else:
                    normalized_title = " ".join(title.casefold().split())
                    normalized_authors = "|".join(
                        str(author).casefold() for author in authors
                    ) if isinstance(authors, list) else ""
                    key = f"title:{normalized_title}|{year}|{normalized_authors}"

        existing_index = positions_by_key.get(key)
        if existing_index is None:
            positions_by_key[key] = len(results)
            results.append(paper)
            continue

        existing = results[existing_index]
        for field, value in paper.items():
            if value in (None, "", []) and existing.get(field) not in (None, "", []):
                continue
            if existing.get(field) in (None, "", []) and value not in (None, "", []):
                existing[field] = value
        if paper.get("open_access") is True:
            existing["open_access"] = True

    return results


async def search_papers(query: str, per_page: int = 10) -> list[dict[str, Any]]:
    from app.services.settings import get_openalex_key
    params = {"search": query, "per-page": per_page}
    key = get_openalex_key()
    headers = {"Authorization": f"Bearer {key}"} if key else {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        response = await client.get(OPENALEX_API_URL, params=params, headers=headers)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise OpenAlexResponseError("OpenAlex returned invalid JSON") from exc

    if not isinstance(data, Mapping) or not isinstance(data.get("results"), list):
        raise OpenAlexResponseError("OpenAlex response did not contain a results list")

    parsed = [
        parse_openalex_work(work)
        for work in data["results"]
        if isinstance(work, Mapping)
    ]
    return deduplicate_papers(parsed)
