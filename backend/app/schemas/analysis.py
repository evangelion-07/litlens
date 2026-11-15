from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    chunk_id: str
    paper_id: str
    paper_title: str
    section: str
    page_number: int | None = None
    source_kind: Literal["pdf", "abstract"]
    excerpt: str = Field(max_length=900)


class SupportingQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    quote: str = Field(min_length=12, max_length=1100)


class EvidenceBacked(BaseModel):
    supporting_quotes: list[SupportingQuote] = Field(default_factory=list, max_length=20)


class PaperClaim(EvidenceBacked):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class SectionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["found", "not_detected", "not_available"]
    summary: str = Field(default="", max_length=5000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


class Coverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["full_text", "partial_text", "abstract_only", "no_text"]
    total_pages: int = Field(ge=0)
    pages_with_text: int = Field(ge=0)
    pages_analyzed: int = Field(ge=0)
    analyzed_units: int = Field(ge=0)
    identified_sections: list[str] = Field(default_factory=list)
    note: str = Field(min_length=1, max_length=2000)


class Weakness(EvidenceBacked):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=2000)
    classification: Literal[
        "author_reported_limitation",
        "confirmed_inconsistency",
        "potential_concern",
        "information_gap",
    ]
    priority: Literal["high", "medium", "low", "not_assessed"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    why_it_matters: str = Field(min_length=1, max_length=2000)
    recommendation: str = Field(min_length=1, max_length=2000)
    scope_note: str = Field(default="", max_length=1500)


class Recommendation(EvidenceBacked):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["high", "medium", "low", "not_assessed"]
    change: str = Field(min_length=1, max_length=2000)
    why: str = Field(min_length=1, max_length=2000)
    how: str = Field(min_length=1, max_length=3000)
    expected_benefit: str = Field(min_length=1, max_length=1500)
    basis: Literal["paper_evidence", "general_review_prompt"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class ResearchGap(EvidenceBacked):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=2000)
    basis_type: Literal["author_stated", "evidence_supported_inference", "speculative"]
    research_question: str = Field(default="", max_length=1500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence: Literal["low", "medium", "high"]
    scope_note: str = Field(min_length=1, max_length=1500)


class PriorityAction(EvidenceBacked):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["high", "medium", "low"]
    action: str = Field(min_length=1, max_length=1500)
    rationale: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    generated_at: str
    analysis_mode: Literal["local_extractive", "provider_assisted"]
    coverage: Coverage
    executive_summary: PaperClaim
    section_summaries: dict[str, SectionSummary]
    key_findings: list[PaperClaim] = Field(default_factory=list, max_length=30)
    strengths: list[PaperClaim] = Field(default_factory=list, max_length=20)
    weaknesses: list[Weakness] = Field(default_factory=list, max_length=30)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=30)
    research_gaps: list[ResearchGap] = Field(default_factory=list, max_length=20)
    priority_action_plan: list[PriorityAction] = Field(default_factory=list, max_length=15)
    evidence: list[EvidenceCitation] = Field(default_factory=list, max_length=5000)
    caveats: list[str] = Field(default_factory=list, max_length=30)
    retrieval: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_references(self) -> "AnalysisReport":
        available = {item.evidence_id for item in self.evidence}
        referenced: list[str] = []
        referenced.extend(self.executive_summary.evidence_ids)
        for section in self.section_summaries.values():
            referenced.extend(section.evidence_ids)
        for collection in (self.key_findings, self.strengths):
            for item in collection:
                referenced.extend(item.evidence_ids)
        for item in self.weaknesses:
            referenced.extend(item.evidence_ids)
        for item in self.recommendations:
            referenced.extend(item.evidence_ids)
        for item in self.research_gaps:
            referenced.extend(item.evidence_ids)
        for item in self.priority_action_plan:
            referenced.extend(item.evidence_ids)
        invalid = sorted(set(referenced) - available)
        if invalid:
            raise ValueError(f"Report contains unknown evidence IDs: {', '.join(invalid)}")
        # For provider-assisted reports, verify that each supporting quote's
        # evidence_id points to an existing evidence entry.  The actual text
        # match is already enforced upstream by checked_quotes(); here we
        # guard the structural contract so the UI can trust the link.
        if self.analysis_mode == "provider_assisted":
            def _check_quote_refs(obj: "EvidenceBacked") -> None:
                for sq in obj.supporting_quotes:
                    if sq.evidence_id not in available:
                        raise ValueError(
                            f"Supporting quote references unknown evidence ID: {sq.evidence_id}"
                        )
            _check_quote_refs(self.executive_summary)
            for item in self.key_findings:
                _check_quote_refs(item)
            for item in self.strengths:
                _check_quote_refs(item)
            for item in self.weaknesses:
                _check_quote_refs(item)
            for item in self.recommendations:
                _check_quote_refs(item)
            for item in self.research_gaps:
                _check_quote_refs(item)
            for item in self.priority_action_plan:
                _check_quote_refs(item)
        return self


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_external_ai: bool = False


class AnalysisJob(BaseModel):
    analysis_id: str
    paper_id: str
    paper_title: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    progress: int = Field(ge=0, le=100)
    error: str | None = None
    report: AnalysisReport | None = None
    created_at: str
    updated_at: str


class AnalysisCapabilities(BaseModel):
    llm_configured: bool
    llm_model: str | None = None
    ocr_available: bool
    crossref_available: bool = True
    max_upload_mb: int
