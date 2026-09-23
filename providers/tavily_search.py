import os
import requests


TAVILY_URL = "https://api.tavily.com/search"


def search_web(query, max_results=5):
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        print("Tavily API key is missing.")
        return []

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }

    try:
        response = requests.post(
            TAVILY_URL,
            json=payload,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("results", [])

    except requests.RequestException as error:
        print(f"Tavily search failed: {error}")
        return []