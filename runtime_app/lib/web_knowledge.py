from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "STELLCODEX/1.0 (+https://stellcodex.local)"


def _safe_snippet(value: str, limit: int = 320) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _duckduckgo_search(query: str, max_results: int, timeout: int) -> list[dict[str, str]]:
    params = urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
    url = f"https://api.duckduckgo.com/?{params}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    results: list[dict[str, str]] = []
    heading = payload.get("Heading")
    abstract_text = payload.get("AbstractText")
    abstract_url = payload.get("AbstractURL")
    if isinstance(heading, str) and isinstance(abstract_text, str) and isinstance(abstract_url, str) and abstract_url:
        results.append(
            {
                "title": heading.strip() or query,
                "url": abstract_url,
                "snippet": _safe_snippet(abstract_text),
                "source": "duckduckgo",
            }
        )

    def add_topic(topic: Any) -> None:
        if not isinstance(topic, dict):
            return
        text = topic.get("Text")
        url_value = topic.get("FirstURL")
        if isinstance(text, str) and isinstance(url_value, str) and url_value:
            title = text.split(" - ", 1)[0].strip() or query
            results.append(
                {
                    "title": title,
                    "url": url_value,
                    "snippet": _safe_snippet(text),
                    "source": "duckduckgo",
                }
            )

    related = payload.get("RelatedTopics")
    if isinstance(related, list):
        for item in related:
            if isinstance(item, dict) and isinstance(item.get("Topics"), list):
                for nested in item["Topics"]:
                    add_topic(nested)
            else:
                add_topic(item)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in results:
        key = row["url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= max_results:
            break
    return deduped


def _wikipedia_search(query: str, max_results: int, timeout: int) -> list[dict[str, str]]:
    params = urlencode(
        {
            "action": "opensearch",
            "search": query,
            "limit": str(max_results),
            "namespace": "0",
            "format": "json",
        }
    )
    url = f"https://en.wikipedia.org/w/api.php?{params}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if not isinstance(payload, list) or len(payload) < 4:
        return []
    titles = payload[1] if isinstance(payload[1], list) else []
    snippets = payload[2] if isinstance(payload[2], list) else []
    links = payload[3] if isinstance(payload[3], list) else []

    rows: list[dict[str, str]] = []
    for idx, title in enumerate(titles):
        if not isinstance(title, str):
            continue
        snippet = snippets[idx] if idx < len(snippets) and isinstance(snippets[idx], str) else ""
        link = links[idx] if idx < len(links) and isinstance(links[idx], str) else ""
        if not link:
            continue
        rows.append(
            {
                "title": title,
                "url": link,
                "snippet": _safe_snippet(snippet),
                "source": "wikipedia",
            }
        )
    return rows


def search_technical_references(query: str, max_results: int = 5, timeout: int = 6) -> list[dict[str, str]]:
    text = (query or "").strip()
    if not text:
        return []

    limit = max(1, min(10, int(max_results)))
    t = max(1, min(20, int(timeout)))

    for fn in (_duckduckgo_search, _wikipedia_search):
        try:
            rows = fn(text, limit, t)
            if rows:
                return rows
        except Exception:
            continue
    return []
