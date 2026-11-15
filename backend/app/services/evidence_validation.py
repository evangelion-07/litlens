"""Source checks shared by chat and reports; these do not prove entailment."""
import re
from collections.abc import Mapping


def checked_quotes(raw, evidence_ids, sources, claim_text=""):
    if not isinstance(raw, list) or not raw or len(raw) > 20:
        raise ValueError("Supporting quotes are missing.")
    ids = set(evidence_ids)
    if not ids or not ids.issubset(sources):
        raise ValueError("Unknown source reference.")
    result = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("Invalid supporting quote.")
        eid = item.get("evidence_id")
        quote = " ".join(str(item.get("quote", "")).split())
        source = " ".join(str(sources.get(eid, "")).split())
        if eid not in ids or not 12 <= len(quote) <= 1100 or quote.casefold() not in source.casefold():
            raise ValueError("Quote is not present in its cited source.")
        result.append({"evidence_id": eid, "quote": quote})
    if {item["evidence_id"] for item in result} != ids:
        raise ValueError("Each citation needs a supporting quote.")
    numbers = lambda text: set(re.findall(r"(?<!\w)[−-]?\d+(?:[.,]\d+)*%?", text))
    if numbers(claim_text) - numbers(" ".join(item["quote"] for item in result)):
        raise ValueError("A numeric claim is absent from its supporting quotes.")
    return result
