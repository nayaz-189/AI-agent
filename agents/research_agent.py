"""Bounded public-document research. No model context, cookies or local files."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from types import MappingProxyType
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request


SOURCES = MappingProxyType({
    "ast": ("https://docs.python.org/3.10/library/ast.html",
            ("abstract syntax", "ast.parse"),
            "The ast module represents Python syntax as a tree. ast.parse produces a tree for inspection."),
    "pathlib": ("https://docs.python.org/3.10/library/pathlib.html",
                ("filesystem paths", "pure paths"),
                "pathlib provides objects for filesystem paths. Pure paths handle path computations without filesystem access."),
})
MAX_BYTES = 2_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Research redirects are not permitted.")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


@dataclass(frozen=True)
class Finding:
    source_id: str
    digest: str
    summary: str


def fetch_source(source_id):
    """Only two fixed HTTPS documents; redirects, proxy credentials and cookies absent."""
    if source_id not in SOURCES:
        raise ValueError("Unregistered research source.")
    url = SOURCES[source_id][0]
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, headers={"User-Agent": "AI-Agent-Public-Research/1", "Accept": "text/html"})
    with opener.open(request, timeout=15) as response:
        if (response.status != 200 or response.geturl() != url
                or response.headers.get_content_type() != "text/html"):
            raise ValueError("Research response rejected.")
        body = response.read(MAX_BYTES + 1)
    return verify_source(source_id, body)


def verify_source(source_id, body):
    if source_id not in SOURCES or type(body) is not bytes or not 0 < len(body) <= MAX_BYTES:
        raise ValueError("Research response rejected.")
    parser = _Text()
    parser.feed(body.decode("utf-8", errors="strict"))
    text = " ".join(" ".join(parser.parts).lower().split())
    if not all(phrase in text for phrase in SOURCES[source_id][1]):
        raise ValueError("Research facts could not be verified.")
    # Downloaded prose never becomes instructions or report content. The bounded
    # reviewed summaries are emitted only after their source anchors are present.
    return Finding(source_id, sha256(body).hexdigest(), SOURCES[source_id][2])


def research_report():
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="public-research") as pool:
        findings = tuple(pool.map(fetch_source, SOURCES))
    if (tuple(f.source_id for f in findings) != tuple(SOURCES)
            or any(f.summary != SOURCES[f.source_id][2] for f in findings)):
        raise ValueError("Research findings rejected.")
    report = "Python AST and pathlib: a bounded research report\n\n"
    for finding in findings:
        report += finding.summary + "\nSource: " + SOURCES[finding.source_id][0] + "\n\n"
    report += "These sources describe Python 3.10. Parsing or computing a path does not grant permission to execute code or access files."
    return report
