import ollama

from brain.model_registry import get_model


def ask_llm(prompt, model_role="strong"):

    model_data = get_model(model_role)

    if not model_data:
        raise ValueError(
            f"Unknown model role: {model_role}"
        )

    model_name = model_data["name"]

    if model_data.get("local") is not True or model_data.get("provider") != "ollama":
        raise ValueError("Runtime planning requires a local Ollama model.")

    # Ignore OLLAMA_HOST and HTTP proxy environment overrides: user commands
    # must not silently leave the machine through a remote model endpoint.
    with ollama.Client(
        host="http://127.0.0.1:11434", trust_env=False, follow_redirects=False,
    ) as client:
        response = client.chat(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            format="json"
        )

    return response["message"]["content"]
