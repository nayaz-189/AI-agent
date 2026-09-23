MODELS = {
    "fast": {
        "name": "qwen3:0.6b",
        "provider": "ollama",
        "role": "Fast lightweight reasoning and routing",
        "local": True
    },

    "strong": {
        "name": "rafw007/gemma4-e4b-claude-coder:latest",
        "provider": "ollama",
        "role": "Complex reasoning and coding",
        "local": True
    }
}


def get_model(model_role):
    model = MODELS.get(model_role)

    if not model:
        return None

    return model