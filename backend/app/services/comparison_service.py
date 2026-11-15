from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

SECTION_ALIASES = {
    "objective": {
        "objective", "objectives", "aim", "aims", "purpose", "research objective",
        "research objectives", "problem statement", "research problem",
    },
    "methods": {
        "method", "methods", "methodology", "materials and methods", "proposed method",
        "approach",
    },
    "experimental_design": {
        "experimental design", "study design", "study protocol", "evaluation protocol",
        "experimental setup", "experiment setup", "experimental protocol",
    },
    "baselines": {
        "baseline", "baselines", "baseline methods", "comparison methods", "competitors",
    },
    "evaluation_metrics": {
        "metric", "metrics", "evaluation metrics", "performance metrics", "evaluation measures",
    },
    "strengths": {"strengths", "advantages", "merits"},
    "research_gaps": {"research gaps", "research gap", "gaps", "open questions"},
    "datasets": {
        "dataset", "datasets", "data set", "data sets", "data collection", "corpus",
        "benchmark", "benchmarks",
    },
    "findings": {
        "result", "results", "findings", "experimental results", "evaluation",
        "conclusion", "conclusions", "results and discussion", "discussion and results",
    },
    "limitations": {
        "limitation", "limitations", "study limitations", "threats to validity", "challenges",
    },
    "future_work": {
        "future work", "future works", "future directions", "future research", "recommendations",
    },
}

_HEADING_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s*")
_SPACE = re.compile(r"\s+")


def _section_heading(line: str) -> str | None:
    normalized = _HEADING_NUMBER.sub("", line.strip())
    normalized = normalized.strip(" :\t-–—").casefold()
    for section, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def extract_sections(pages: Sequence[Mapping[str, Any]], abstract: str | None = None) -> dict[str, dict[str, Any]]:
    from app.services.document_structure import aggregate_sections
    mapping = {"objectives": "objective", "problem_statement": "objective", "methodology": "methods",
               "results": "findings", "discussion": "findings", "conclusion": "findings"}
    output = {}
    for name, section in aggregate_sections(pages).items():
        field = mapping.get(name, name)
        if field not in SECTION_ALIASES:
            continue
        entry = output.setdefault(field, {"text": "", "page_numbers": [], "source_kind": "pdf_section"})
        entry["text"] = (entry["text"] + " " + section["text"]).strip()
        entry["page_numbers"] = list(dict.fromkeys(entry["page_numbers"] + section["page_numbers"]))
    if "objective" not in output and abstract and abstract.strip():
        output["objective"] = {"text": abstract.strip(), "page_numbers": [], "source_kind": "abstract"}
    return output


def compare_papers(papers_with_pages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a side-by-side comparison from stored metadata and explicitly headed text."""
    papers = []
    author_counts: Counter[str] = Counter()
    author_labels: dict[str, str] = {}
    years = []
    reported_limitations = []
    reported_future_work = []

    for item in papers_with_pages:
        paper = item["paper"]
        sections = extract_sections(item.get("pages", []), paper.get("abstract"))
        authors = paper.get("authors") or []
        for author in authors:
            normalized_author = str(author).casefold().strip()
            if normalized_author:
                author_counts[normalized_author] += 1
                author_labels.setdefault(normalized_author, str(author))
        year = paper.get("publication_year")
        if isinstance(year, int):
            years.append(year)

        entry = {
            "paper_id": paper["id"],
            "title": paper["title"],
            "year": year,
            "doi": paper.get("doi"),
            "authors": authors,
            "source_type": paper.get("source_type"),
            "processing_status": paper.get("processing_status"),
            "sections": sections,
        }
        papers.append(entry)

        for field, destination, label in (
            ("limitations", reported_limitations, "author_reported_limitation"),
            ("future_work", reported_future_work, "author_reported_future_work"),
        ):
            section = sections.get(field)
            if section:
                destination.append({
                    "paper_id": paper["id"],
                    "title": paper["title"],
                    "page_numbers": section["page_numbers"],
                    "text": section["text"],
                    "evidence_type": label,
                })

    potential_gaps = []
    for evidence in reported_future_work:
        potential_gaps.append({
            "statement": "A possible direction to review is the future work explicitly described in this selected paper.",
            "basis": evidence["text"],
            "evidence_type": evidence["evidence_type"],
            "supporting_paper_id": evidence["paper_id"],
            "supporting_paper_title": evidence["title"],
            "page_numbers": evidence["page_numbers"],
            "confidence": "low",
            "scope_note": "This is limited to the selected papers and does not establish global novelty.",
        })
    for evidence in reported_limitations:
        potential_gaps.append({
            "statement": "A possible direction to review is whether the reported limitation can be addressed in further work.",
            "basis": evidence["text"],
            "evidence_type": evidence["evidence_type"],
            "supporting_paper_id": evidence["paper_id"],
            "supporting_paper_title": evidence["title"],
            "page_numbers": evidence["page_numbers"],
            "confidence": "low",
            "scope_note": "This is limited to the selected papers and does not establish global novelty.",
        })

    return {
        "papers": papers,
        "shared_authors": [author_labels[name] for name, count in author_counts.items() if count > 1],
        "publication_year_range": [min(years), max(years)] if years else None,
        "reported_limitations": reported_limitations,
        "reported_future_work": reported_future_work,
        "potential_gaps": potential_gaps,
        "analysis_note": (
            "Sections are included only when an explicit heading was recognized; objectives may use an indexed abstract. "
            "Gap directions are hypotheses based on the selected papers, not novelty claims."
        ),
    }
