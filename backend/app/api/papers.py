import httpx
from fastapi import APIRouter, HTTPException, Query

from app.schemas.paper import CrossrefMetadata
from app.services.crossref_service import (
    CrossrefMetadataError,
    CrossrefNotFound,
    CrossrefUnavailable,
    verify_crossref_doi,
)
from app.services.openalex_service import OpenAlexResponseError, search_papers

router = APIRouter(prefix="/papers", tags=["Papers"])


@router.get("/search")
async def search_research_papers(
    q: str = Query(min_length=2, max_length=200),
    per_page: int = Query(default=10, ge=1, le=25),
):
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Query must contain at least two non-space characters.")

    try:
        papers = await search_papers(query=query, per_page=per_page)
        return {"query": query, "count": len(papers), "results": papers}
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="OpenAlex did not respond before the request timed out.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=503,
                detail="OpenAlex is temporarily rate limiting requests. Try again shortly.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="OpenAlex returned an unsuccessful response.",
        ) from exc
    except OpenAlexResponseError as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAlex returned an invalid response.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to OpenAlex. Check your network.",
        ) from exc


@router.get("/crossref/verify", response_model=CrossrefMetadata)
async def verify_doi_with_crossref(doi: str = Query(min_length=5, max_length=255)):
    try:
        return await verify_crossref_doi(doi)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CrossrefNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CrossrefUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CrossrefMetadataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc