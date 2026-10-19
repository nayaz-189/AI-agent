import ollama

from brain.model_registry import get_model


def ask_llm(prompt, model_role="strong", *, timeout_seconds=None, max_tokens=None):

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
    client_options = {"host": "http://127.0.0.1:11434", "trust_env": False, "follow_redirects": False}
    chat_options = {}
    if timeout_seconds is not None:
        if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 60:
            raise ValueError("Invalid local inference timeout.")
        client_options["timeout"] = timeout_seconds
    if max_tokens is not None:
        if type(max_tokens) is not int or not 1 <= max_tokens <= 512:
            raise ValueError("Invalid local response limit.")
        chat_options["options"] = {"num_predict": max_tokens, "num_ctx": 2048}
        chat_options["think"] = False
    with ollama.Client(**client_options) as client:
        response = client.chat(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            format="json",
            **chat_options,
        )

    return response["message"]["content"]
