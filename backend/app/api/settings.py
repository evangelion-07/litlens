import httpx
from fastapi import APIRouter, HTTPException

from app.services.settings import Settings, get_settings, save_settings
from app.services.model_status import model_readiness

router = APIRouter(prefix="/settings", tags=["Models and preferences"])


@router.get("")
def read_settings():
    return get_settings()


@router.put("")
def update_settings(body: Settings):
    try:
        return save_settings(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/models")
async def installed_models():
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(settings["ollama_url"].rstrip("/") + "/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
            active_models = None
            try:
                active_response = await client.get(settings["ollama_url"].rstrip("/") + "/api/ps")
                active_response.raise_for_status()
                active_models = active_response.json().get("models", [])
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                # Older Ollama builds may not expose the loaded-model endpoint.
                pass
        return model_readiness(
            settings,
            [{"name": m["name"], "size": m.get("size")} for m in models],
            True,
            active_models=active_models,
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return model_readiness(settings, [], False, "Ollama is unreachable. Start Ollama, then refresh.")
