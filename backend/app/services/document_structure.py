from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

SECTION_LABELS = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "related_work": "Related work",
    "problem_statement": "Problem statement",
    "objectives": "Objectives",
    "contributions": "Contributions",
    "methodology": "Methodology",
    "architecture": "System architecture",
    "datasets": "Datasets",
    "experiments": "Experiments",
    "experimental_design": "Experimental design",
    "baselines": "Baselines",
    "evaluation_metrics": "Evaluation metrics",
    "strengths": "Strengths",
    "research_gaps": "Research gaps",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "limitations": "Limitations",
    "future_work": "Future work",
    "references": "References",
    "unclassified": "Other extracted text",
}

SECTION_ALIASES = {
    "abstract": {"abstract"},
    "introduction": {"introduction", "background and motivation"},
    "related_work": {
        "related work", "related works", "literature review", "related literature",
        "state of the art", "background", "prior work",
    },
    "problem_statement": {
        "problem", "problem statement", "research problem", "problem formulation",
        "motivation", "research motivation",
    },
    "objectives": {
        "objective", "objectives", "aim", "aims", "research objective",
        "research objectives", "research question", "research questions",
    },
    "contributions": {
        "contribution", "contributions", "main contributions", "our contributions",
        "novelty", "key contributions",
    },
    "methodology": {
        "method", "methods", "methodology", "materials and methods", "proposed method",
        "proposed approach", "approach",
        "methodological approach",
    },
    "architecture": {
        "system architecture", "model architecture", "architecture", "framework",
        "proposed system", "system design",
    },
    "datasets": {
        "dataset", "datasets", "data set", "data sets", "data collection", "corpus",
        "benchmark", "benchmarks",
    },
    "experiments": {
        "experiment", "experiments", "experimental evaluation", "evaluation",
        "implementation details",
    },
    "results": {
        "result", "results", "findings", "experimental results", "quantitative results",
        "performance evaluation", "results and analysis",
    },
    "discussion": {
        "discussion", "results and discussion", "discussion and results",
        "analysis and discussion",
    },
    "conclusion": {"conclusion", "conclusions", "concluding remarks"},
    "limitations": {
        "limitation", "limitations", "study limitations", "threats to validity",
        "threats to validity and limitations", "challenges",
    },
    "future_work": {
        "future work", "future works", "future directions", "future research",
        "research directions", "recommendations",
    },
    "references": {"references", "bibliography", "works cited"},
    "experimental_design": {"experimental design", "study design", "study protocol", "evaluation protocol", "experimental setup", "experiment setup", "experimental protocol"},
    "baselines": {"baseline", "baselines", "baseline methods", "comparison methods", "competitors"},
    "evaluation_metrics": {"metric", "metrics", "evaluation metrics", "performance metrics", "evaluation measures"},
    "strengths": {"strengths", "advantages", "merits"},
    "research_gaps": {"research gaps", "research gap", "gaps", "open questions"},
}

_NUMBER_PREFIX = re.compile(r"^\s*(?:(?:\d+(?:\.\d+)*|[ivxlcdm]+)[.)]?\s+)", re.IGNORECASE)
_SPACE = re.compile(r"\s+")


def detect_section_heading(line: str) -> str | None:
    """Recognize short, explicit academic section headings without guessing from body text."""
    value = str(line or "").strip().lstrip("#").strip()
    if not value or len(value) > 120:
        return None

    numbered = bool(_NUMBER_PREFIX.match(value))
    value = _NUMBER_PREFIX.sub("", value)
    value = value.strip().strip(":").strip()
    normalized = _SPACE.sub(" ", value).strip(" .:;-–—\t").casefold()
    if not normalized:
        return None

    for section, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section
        # Same-line heading suffixes are accepted only when the line is numbered
        # or explicitly title-like; this avoids interpreting ordinary prose as headings.
        if numbered or line.strip().isupper():
            for alias in aliases:
                if normalized.startswith(alias + ":") or normalized.startswith(alias + " -"):
                    return section
    return None


def split_page_sections(
    page_number: int,
    text: str,
    active_section: str = "unclassified",
) -> tuple[list[dict[str, Any]], str]:
    """Split one page at recognized headings, carrying the current section across pages."""
    passages: list[dict[str, Any]] = []
    current = active_section
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        buffer.clear()
        if content:
            passages.append({
                "section": current,
                "section_label": SECTION_LABELS.get(current, current.replace("_", " ").title()),
                "page_number": int(page_number),
                "text": content,
            })

    for line in str(text or "").splitlines():
        heading = detect_section_heading(line)
        if heading:
            flush()
            current = heading
        elif line.strip():
            buffer.append(line.strip())
    flush()
    return passages, current


def sectionize_pages(pages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return every non-empty page passage, preserving heading and page provenance."""
    active = "unclassified"
    passages: list[dict[str, Any]] = []
    for page in pages:
        page_number = int(page.get("page_number", 0) or 0)
        page_passages, active = split_page_sections(
            page_number,
            str(page.get("text", "") or ""),
            active,
        )
        passages.extend(page_passages)
    return passages


def aggregate_sections(pages: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate section passages while retaining page-local evidence boundaries."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for passage in sectionize_pages(pages):
        grouped[passage["section"]].append(passage)

    result: dict[str, dict[str, Any]] = {}
    for key, passages in grouped.items():
        result[key] = {
            "label": SECTION_LABELS.get(key, key.replace("_", " ").title()),
            "text": "\n".join(passage["text"] for passage in passages),
            "page_numbers": list(dict.fromkeys(passage["page_number"] for passage in passages)),
            "passages": passages,
        }
    return result
