from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


def _refs(item: Mapping[str, Any]) -> str:
    values = item.get("evidence_ids") or []
    refs = " " + " ".join(f"[{value}]" for value in values) if values else ""
    for quote in item.get("supporting_quotes") or []:
        refs += "\n\n> " + " ".join(quote["quote"].split()) + " [" + quote["evidence_id"] + "]"
    return refs


def report_markdown(report: Mapping[str, Any]) -> str:
    coverage = report.get("coverage") or {}
    lines = [
        f"# {report.get('title') or 'Paper analysis'}",
        "",
        f"**LitLens paper analysis** · {report.get('generated_at', '')}",
        "",
        "## Coverage and method",
        "",
        f"- Scope: **{coverage.get('scope', 'unknown').replace('_', ' ')}**",
        f"- Pages analyzed: {coverage.get('pages_analyzed', 0)} of {coverage.get('total_pages', 0)}",
        f"- Evidence units: {coverage.get('analyzed_units', 0)}",
        f"- Mode: {str(report.get('analysis_mode', '')).replace('_', ' ')}",
        f"- Retrieval: {str((report.get('retrieval') or {}).get('mode', 'not recorded'))}",
        f"- Coverage note: {coverage.get('note', '')}",
        "",
        "## Executive summary",
        "",
        str((report.get("executive_summary") or {}).get("text", "")) + _refs(report.get("executive_summary") or {}),
        "",
        "## Section-by-section analysis",
        "",
    ]
    section_summaries = report.get("section_summaries") or {}
    for key, value in section_summaries.items():
        lines.extend([
            f"### {key.replace('_', ' ').title()} · {value.get('status', 'unknown').replace('_', ' ')}",
            "",
            str(value.get("summary") or "Not available.") + _refs(value),
            "",
        ])

    for title, key in (
        ("Key findings", "key_findings"),
        ("Strengths", "strengths"),
        ("Potential weaknesses and limitations", "weaknesses"),
    ):
        lines.extend([f"## {title}", ""])
        items = report.get(key) or []
        if not items:
            lines.extend(["No evidence-supported items were produced in this analysis mode.", ""])
        for item in items:
            if key == "weaknesses":
                label = f"{item.get('classification', '').replace('_', ' ')} · {item.get('priority', 'not assessed')}"
                lines.extend([
                    f"### {label}",
                    "",
                    str(item.get("statement", "")) + _refs(item),
                    "",
                    f"Why it matters: {item.get('why_it_matters', '')}",
                    "",
                    f"Suggested correction: {item.get('recommendation', '')}",
                    "",
                    f"Scope: {item.get('scope_note', '')}",
                    "",
                ])
            else:
                lines.extend([f"- {item.get('text', '')}{_refs(item)}", ""])

    lines.extend(["## Prioritized improvements", ""])
    for item in report.get("recommendations") or []:
        lines.extend([
            f"### {item.get('priority', 'not assessed').title()} · {item.get('change', '')}",
            "",
            f"Why: {item.get('why', '')}",
            "",
            f"How: {item.get('how', '')}",
            "",
            f"Expected benefit: {item.get('expected_benefit', '')}{_refs(item)}",
            "",
        ])

    lines.extend(["## Research gaps and future directions", ""])
    gaps = report.get("research_gaps") or []
    if not gaps:
        lines.extend(["No source-supported research gaps were extracted.", ""])
    for item in gaps:
        lines.extend([
            f"### {item.get('basis_type', '').replace('_', ' ').title()} · {item.get('confidence', 'low')} confidence",
            "",
            str(item.get("statement", "")) + _refs(item),
            "",
            f"Possible research question: {item.get('research_question', '')}",
            "",
            f"Scope: {item.get('scope_note', '')}",
            "",
        ])

    lines.extend(["## Priority action plan", ""])
    for index, item in enumerate(report.get("priority_action_plan") or [], start=1):
        lines.extend([
            f"{index}. **{item.get('priority', '').title()}** — {item.get('action', '')}{_refs(item)}",
            f"   {item.get('rationale', '')}",
            "",
        ])

    lines.extend(["## Evidence register", ""])
    for item in report.get("evidence") or []:
        location = f"page {item['page_number']}" if item.get("page_number") else "abstract"
        lines.extend([
            f"### [{item.get('evidence_id')}] {item.get('paper_title')} · {item.get('section')} · {location}",
            "",
            str(item.get("excerpt", "")),
            "",
        ])

    lines.extend(["## Limitations and caveats", ""])
    for item in report.get("caveats") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _plain_ascii(text: str) -> str:
    replacements = {
        "—": "-", "–": "-", "−": "-", "“": '"', "”": '"',
        "‘": "'", "’": "'", "…": "...", "·": "|", "→": "->",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _wrap(text: str, font: Any, size: float, width: float) -> list[str]:
    words = _plain_ascii(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if font.text_length(candidate, fontsize=size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def report_pdf(report: Mapping[str, Any]) -> bytes:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF export requires PyMuPDF, which is listed in backend requirements.") from exc

    markdown = report_markdown(report)
    document = pymupdf.open()
    page_width, page_height = 595.0, 842.0
    left, right, top, bottom = 54.0, 54.0, 60.0, 54.0
    normal_font = pymupdf.Font("helv")
    bold_font = pymupdf.Font("hebo")
    page = document.new_page(width=page_width, height=page_height)
    y = top

    def new_page() -> None:
        nonlocal page, y
        page = document.new_page(width=page_width, height=page_height)
        y = top

    for source_line in markdown.splitlines():
        stripped = source_line.strip()
        if not stripped:
            y += 7
            continue
        if stripped.startswith("# "):
            text, size, font, gap = stripped[2:], 20.0, bold_font, 13.0
        elif stripped.startswith("## "):
            text, size, font, gap = stripped[3:], 14.0, bold_font, 9.0
        elif stripped.startswith("### "):
            text, size, font, gap = stripped[4:], 11.0, bold_font, 5.0
        elif stripped.startswith("- "):
            text, size, font, gap = "- " + stripped[2:], 9.5, normal_font, 2.0
        else:
            text, size, font, gap = stripped, 9.5, normal_font, 2.0
        for line in _wrap(text, font, size, page_width - left - right):
            line_height = size * 1.45
            if y + line_height > page_height - bottom:
                new_page()
            page.insert_text((left, y), line, fontname="hebo" if font is bold_font else "helv", fontsize=size)
            y += line_height
        y += gap

    total = len(document)
    for number, current_page in enumerate(document, start=1):
        current_page.draw_line(
            (left, page_height - 38), (page_width - right, page_height - 38),
            color=(0.78, 0.82, 0.80), width=0.6,
        )
        current_page.insert_text(
            (left, page_height - 24), "LitLens | Evidence-first paper analysis",
            fontname="helv", fontsize=8, color=(0.30, 0.38, 0.34),
        )
        footer = f"{number} / {total}"
        current_page.insert_text(
            (page_width - right - normal_font.text_length(footer, fontsize=8), page_height - 24),
            footer, fontname="helv", fontsize=8, color=(0.30, 0.38, 0.34),
        )
    document.set_metadata({
        "title": f"LitLens analysis - {report.get('title', 'Paper')}",
        "author": "LitLens",
        "subject": "Evidence-grounded research paper analysis",
    })
    result = document.tobytes(garbage=4, deflate=True)
    document.close()
    return result


def safe_report_filename(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title or "paper-analysis").strip("-._")
    return (slug or "paper-analysis")[:80]
