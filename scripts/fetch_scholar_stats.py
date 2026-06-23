"""Fetch citation metrics and recent publications from Google Scholar.

Run on a schedule by .github/workflows/scholar-stats.yml so the README badges
and publication list stay close to current without scraping Google on every
profile page view.
"""

import difflib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from scholarly import scholarly

SCHOLAR_ID = "Wc_-IPYAAAAJ"
SCHOLAR_PROFILE_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"
RECENT_PUBLICATIONS_COUNT = 5
CROSSREF_TITLE_MATCH_THRESHOLD = 0.8

ROOT = Path(__file__).resolve().parent.parent
STATS_PATH = ROOT / "scholar-stats.json"
README_PATH = ROOT / "README.md"

README_START_MARKER = "<!-- SCHOLAR-PUBLICATIONS:START -->"
README_END_MARKER = "<!-- SCHOLAR-PUBLICATIONS:END -->"


def _pub_year(pub: dict) -> int:
    try:
        return int(pub.get("bib", {}).get("pub_year", 0))
    except (TypeError, ValueError):
        return 0


def fetch_doi(title: str) -> str | None:
    """Look up a publication's DOI on Crossref by title, skipping supplementary components."""
    query = urllib.parse.urlencode({"query.bibliographic": title, "rows": 5})
    url = f"https://api.crossref.org/works?{query}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    best_doi, best_score = None, 0.0
    for item in data.get("message", {}).get("items", []):
        if item.get("type") == "component":
            continue
        candidate_title = " ".join(item.get("title", []))
        score = difflib.SequenceMatcher(None, title.lower(), candidate_title.lower()).ratio()
        if score > best_score:
            best_score, best_doi = score, item.get("DOI")

    return best_doi if best_score >= CROSSREF_TITLE_MATCH_THRESHOLD else None


def fetch_recent_publications(author: dict, limit: int = RECENT_PUBLICATIONS_COUNT) -> list[dict]:
    pubs = sorted(author.get("publications", []), key=_pub_year, reverse=True)
    recent = []
    for pub in pubs[:limit]:
        bib = pub.get("bib", {})
        title = bib.get("title", "Untitled")
        doi = fetch_doi(title)
        url = f"https://doi.org/{doi}" if doi else pub.get("pub_url", SCHOLAR_PROFILE_URL)
        recent.append(
            {
                "title": title,
                "year": bib.get("pub_year", ""),
                "venue": bib.get("citation", ""),
                "doi": doi,
                "url": url,
            }
        )
    return recent


def render_publications_markdown(pubs: list[dict]) -> str:
    lines = []
    for pub in pubs:
        entry = f"- [{pub['title']}]({pub['url']})"
        if pub.get("venue"):
            entry += f" — {pub['venue']}"
        lines.append(entry)
    return "\n".join(lines)


def update_readme(pubs: list[dict]) -> None:
    text = README_PATH.read_text()
    if README_START_MARKER not in text or README_END_MARKER not in text:
        return
    pre, rest = text.split(README_START_MARKER, 1)
    _, post = rest.split(README_END_MARKER, 1)
    block = f"{README_START_MARKER}\n{render_publications_markdown(pubs)}\n{README_END_MARKER}"
    README_PATH.write_text(pre + block + post)


def main() -> None:
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=["indices", "publications"])

    recent_publications = fetch_recent_publications(author)

    stats = {
        "citations": author.get("citedby", 0),
        "citations_5y": author.get("citedby5y", 0),
        "hindex": author.get("hindex", 0),
        "hindex_5y": author.get("hindex5y", 0),
        "i10index": author.get("i10index", 0),
        "i10index_5y": author.get("i10index5y", 0),
        "recent_publications": recent_publications,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n")
    update_readme(recent_publications)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
