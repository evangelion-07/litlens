"""Model installation readiness, independent of the Ollama network call."""


def model_readiness(settings, models, available, message=None, active_models=None):
    names = {item["name"] for item in models}

    def installed(name):
        return name in names or (":" not in name and name + ":latest" in names)

    chat_ready = available and installed(settings["ollama_model"])
    embeddings_ready = available and installed(settings["embedding_model"])

    def is_active(name):
        if active_models is None:
            return None
        return any(
            model.get("name") == name
            or (":" not in name and model.get("name") == name + ":latest")
            or model.get("model") == name
            for model in active_models
        )

    chat_loaded = is_active(settings["ollama_model"])
    embeddings_loaded = is_active(settings["embedding_model"])
    required = []
    if settings["provider"] == "ollama" and not chat_ready:
        required.append(settings["ollama_model"])
    if settings["embeddings_enabled"] and not embeddings_ready:
        required.append(settings["embedding_model"])
    missing = list(dict.fromkeys(required))
    return {
        "available": available, "models": models, "chat_ready": chat_ready,
        "embeddings_ready": embeddings_ready, "chat_loaded": chat_loaded,
        "embeddings_loaded": embeddings_loaded, "ready": not missing,
        "missing_models": missing,
        "message": message or (
            "Download missing models: " + ", ".join(missing) if missing else
            "Ollama is working; the selected chat model is loaded." if chat_loaded else
            "Ollama is connected; the selected chat model is installed and will load when used."
        ),
    }
