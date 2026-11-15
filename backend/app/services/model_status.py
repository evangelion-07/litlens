"""Model installation readiness, independent of the Ollama network call."""


def model_readiness(settings, models, available, message=None):
    names = {item["name"] for item in models}

    def installed(name):
        return name in names or (":" not in name and name + ":latest" in names)

    chat_ready = available and installed(settings["ollama_model"])
    embeddings_ready = available and installed(settings["embedding_model"])
    required = []
    if settings["provider"] == "ollama" and not chat_ready:
        required.append(settings["ollama_model"])
    if settings["embeddings_enabled"] and not embeddings_ready:
        required.append(settings["embedding_model"])
    missing = list(dict.fromkeys(required))
    return {
        "available": available, "models": models, "chat_ready": chat_ready,
        "embeddings_ready": embeddings_ready, "ready": not missing,
        "missing_models": missing,
        "message": message or ("Download missing models: " + ", ".join(missing) if missing else "Selected local models are installed."),
    }
