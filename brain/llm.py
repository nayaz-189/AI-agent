import ollama

from brain.model_registry import get_model


def ask_llm(prompt, model_role="strong"):

    model_data = get_model(model_role)

    if not model_data:
        raise ValueError(
            f"Unknown model role: {model_role}"
        )

    model_name = model_data["name"]

    response = ollama.chat(
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