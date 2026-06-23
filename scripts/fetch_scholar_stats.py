"""Fetch citation metrics and recent publications from Google Scholar.

Run on a schedule by .github/workflows/scholar-stats.yml so the README badges
and publication list stay close to current without scraping Google on every
profile page view.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from scholarly import scholarly

SCHOLAR_ID = "Wc_-IPYAAAAJ"
SCHOLAR_PROFILE_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"
RECENT_PUBLICATIONS_COUNT = 5

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


def fetch_recent_publications(author: dict, limit: int = RECENT_PUBLICATIONS_COUNT) -> list[dict]:
    pubs = sorted(author.get("publications", []), key=_pub_year, reverse=True)
    recent = []
    for pub in pubs[:limit]:
        bib = pub.get("bib", {})
        author_pub_id = pub.get("author_pub_id", "")
        url = pub.get("pub_url") or (
            f"https://scholar.google.com/citations?view_op=view_citation&hl=en"
            f"&user={SCHOLAR_ID}&citation_for_view={author_pub_id}"
            if author_pub_id
            else SCHOLAR_PROFILE_URL
        )
        recent.append(
            {
                "title": bib.get("title", "Untitled"),
                "year": bib.get("pub_year", ""),
                "venue": bib.get("citation", ""),
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
