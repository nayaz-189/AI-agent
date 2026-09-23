import webbrowser
import subprocess
import os

from brain.application_resolver import find_application
from urllib.parse import quote_plus

from brain.website_cache import (
    get_cached_website,
    save_website,
)

from brain.website_resolver import resolve_official_website


def open_youtube():
    webbrowser.open("https://www.youtube.com")


def open_google():
    webbrowser.open("https://www.google.com")


def open_calculator():
    subprocess.Popen("calc.exe")


def open_website(url):
    webbrowser.open(url)


def resolve_website(target):
    target = target.lower().strip()

    print(f"Resolver received target: {target}")

    # 1. Memory/cache first
    cached_url = get_cached_website(target)

    if cached_url:
        print(f"Cache hit: {cached_url}")
        webbrowser.open(cached_url)
        return

    # 2. Search + identity resolution
    print("Cache miss. Searching for official website...")

    resolved_url = resolve_official_website(target)

    # 3. High-confidence result
    if resolved_url:
        print(f"Resolved website: {resolved_url}")

        save_website(target, resolved_url)

        print(
            f"Saved to cache: "
            f"{target} -> {resolved_url}"
        )

        webbrowser.open(resolved_url)
        return

    # 4. Resolver was uncertain — don't cache
    print("Could not safely identify official website.")

    query = quote_plus(
        f"{target} official website"
    )

    search_url = (
        "https://www.google.com/search?q="
        + query
    )

    print("Opening search results instead.")

    webbrowser.open(search_url)

def resolve_application(target):
    print(f"Application resolver received: {target}")

    app = find_application(target)

    if not app:
        print("Could not safely identify application.")
        return False

    print(
        f"Resolved application: "
        f"{app['name']} ({app['score']}%)"
    )

    try:
        os.startfile(app["path"])

        print(f"Opened application: {app['name']}")
        return True

    except OSError as error:
        print(f"Failed to open application: {error}")
        return False

def launch_application(path):
    print(f"Launching application: {path}")

    if not os.path.exists(path):
        print("Application shortcut no longer exists.")
        return False

    try:
        os.startfile(path)
        return True

    except OSError as error:
        print(f"Failed to launch application: {error}")
        return False