import json
from pathlib import Path


CACHE_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "website_cache.json"
)


def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_cached_website(target):
    cache = load_cache()

    key = target.lower().strip()

    return cache.get(key)


def save_website(target, url):
    cache = load_cache()

    key = target.lower().strip()

    cache[key] = url

    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            cache,
            file,
            indent=4
        )