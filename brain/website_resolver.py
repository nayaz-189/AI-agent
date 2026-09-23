from urllib.parse import urlparse

from providers.tavily_search import search_web
COMMON_SERVICE_TLDS = {
    "com",
    "org",
    "net",
    "io",
    "ai",
    "co",
    "app",
    "dev",
    "design",
}

def normalize_name(text):
    return "".join(
        character
        for character in text.lower()
        if character.isalnum()
    )


def get_domain(url):
    try:
        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def resolve_official_website(target):
    target_normalized = normalize_name(target)

    results = search_web(
        f"{target} official website",
        max_results=10,
    )

    if not results:
        return None

    candidates = []

    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")

        domain = get_domain(url)

        if not domain:
            continue

        root_name = domain.split(".")[0]
        root_normalized = normalize_name(root_name)

        score = 0
        domain_parts = domain.split(".")

        # Prefer normal two-part root domains such as:
        # github.com
        # huggingface.co
        #
        # over secondary branded domains such as:
        # github.blog
        if len(domain_parts) == 2:
                    common_service_tlds = {
            "com",
            "org",
            "net",
            "io",
            "ai",
            "co",
            "app",
            "dev",
            "design",
        }

        tld = domain_parts[-1]

        if tld in COMMON_SERVICE_TLDS:
            score += 20
            score += 30

        # Strong signal:
        # github -> github.com
        # hugging face -> huggingface.co
        if root_normalized == target_normalized:
            score += 100

        # Weaker signal:
        # target appears inside domain
        elif target_normalized in normalize_name(domain):
            score += 40

        # Search title matches target
        if target_normalized in normalize_name(title):
            score += 20

        candidates.append(
            {
                "url": url,
                "domain": domain,
                "title": title,
                "score": score,
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: candidate["score"],
        reverse=True,
    )

    print("\nResolver candidates:")

    for candidate in candidates[:5]:
        print(
            candidate["score"],
            candidate["domain"],
            candidate["title"],
        )

    best = candidates[0]

    # Don't automatically trust weak matches.
    if best["score"] < 100:
        return None

    return f"https://{best['domain']}"