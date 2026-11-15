from app.services.analysis_service import build_evidence_units
from app.services.retrieval_service import retrieve_evidence, keyword_search


async def review_retrieval(paper, pages, chunks):
    units = build_evidence_units(paper, pages, chunks)
    by_chunk = {u["chunk_id"]: u["evidence_id"] for u in units}
    topics = {
        "methods": "method methodology proposed approach architecture",
        "datasets": "dataset data collection sample participants",
        "evaluation": "results accuracy precision recall baseline evaluation experiment",
        "limitations": "limitations threats validity bias generalization",
        "future_work": "future work research gaps further investigation",
    }
    overview = {"mode": "keyword", "indexed_chunks": len(units), "focus": {}, "notice": None}
    unavailable = False
    for name, query in topics.items():
        if unavailable:
            evidence = keyword_search(query, units, 3)
        else:
            evidence, mode, notice = await retrieve_evidence(query, units, 3)
            overview["mode"] = mode
            if notice:
                overview["notice"] = notice
            unavailable = mode == "keyword-fallback"
        overview["focus"][name] = [
            {"evidence_id": by_chunk[item["chunk_id"]], "page_number": item.get("page_number"),
             "text": item["text"][:650]} for item in evidence
        ]
    return overview
