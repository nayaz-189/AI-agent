import time
import ollama


MODELS = [
    "qwen3:0.6b",
    "rafw007/gemma4-e4b-claude-coder:latest"
]


PROMPT = """
Return only JSON.

User request:
open github

Required output format:
{
    "tool": "open_website",
    "arguments": {
        "url": "https://github.com"
    }
}
"""


for model in MODELS:

    print(f"\nTesting: {model}")

    start = time.perf_counter()

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": PROMPT
            }
        ],
        format="json"
    )

    end = time.perf_counter()

    print("Time:", round(end - start, 2), "seconds")
    print("Response:")
    print(response["message"]["content"])