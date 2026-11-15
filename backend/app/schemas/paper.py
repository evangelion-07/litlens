from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    openalex_id: str | None = None
    title: str = Field(min_length=1, max_length=2000)
    authors: list[str] = Field(default_factory=list, max_length=200)
    year: int | None = None
    doi: str | None = None
    abstract: str | None = None
    publication_type: str | None = None
    cited_by_count: int | None = None
    open_access: bool = False
    landing_page_url: str | None = None
    pdf_url: str | None = None


class CrossrefMetadata(BaseModel):
    source: str = "Crossref"
    doi: str
    verified: bool
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    publication_type: str | None = None
    publisher: str | None = None
    container_title: str | None = None
    url: str | None = None
    abstract: str | None = None