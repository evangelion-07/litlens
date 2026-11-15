from fastapi import APIRouter, Query
import json

from app.schemas.assistant import QuestionRequest
from app.services.assistant_service import answer_question
from app.services.library_repository import get_evidence_documents, get_paper, _connection, init_db
from app.services.llm_provider import configured_llm_provider
from fastapi import HTTPException

router = APIRouter(prefix="/assistant", tags=["Research assistant"])


@router.post("/ask")
async def ask_question(request: QuestionRequest):
    if any(get_paper(paper_id) is None for paper_id in request.paper_ids):
        raise HTTPException(404, "A selected paper is not in your library.")
    provider = configured_llm_provider() if request.use_llm else None
    if request.use_llm and provider is None:
        raise HTTPException(422, "Choose an Ollama or API model in Settings, or turn off AI answers.")
    documents = get_evidence_documents(request.paper_ids or None)
    result = await answer_question(
        request.question, documents, top_k=request.top_k,
        conversation=[turn.model_dump() for turn in request.conversation],
        llm_provider=provider, use_configured_llm=False,
    )
    if len(request.paper_ids) == 1:
        with _connection() as db:
            # If the paper was deleted while the model ran, don't recreate its history.
            if db.execute("SELECT id FROM papers WHERE id=?", (request.paper_ids[0],)).fetchone():
                db.execute("INSERT INTO chat_turns(paper_id, role, content) VALUES (?, 'user', ?)",
                           (request.paper_ids[0], request.question))
                details = {key: result.get(key) for key in ("citations", "answer_mode", "retrieval_mode", "message")}
                db.execute("INSERT INTO chat_turns(paper_id, role, content, details) VALUES (?, 'assistant', ?, ?)",
                           (request.paper_ids[0], result["answer"], json.dumps(details)))
    return result


@router.get("/history")
def history(paper_id: str = Query(min_length=1, max_length=100)):
    if get_paper(paper_id) is None:
        raise HTTPException(404, "Paper is not in your library.")
    with _connection() as db:
        rows = db.execute("SELECT role, content, details FROM chat_turns WHERE paper_id=? ORDER BY id DESC LIMIT 100", (paper_id,)).fetchall()
    return {"turns": [{"role": r["role"], "content": r["content"], **json.loads(r["details"])} for r in reversed(rows)]}


@router.delete("/history")
def clear_history(paper_id: str = Query(min_length=1, max_length=100)):
    if get_paper(paper_id) is None:
        raise HTTPException(404, "Paper is not in your library.")
    with _connection() as db:
        db.execute("DELETE FROM chat_turns WHERE paper_id=?", (paper_id,))
    return {"cleared": True}
