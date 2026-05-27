#!/usr/bin/env python3
"""
Update AI × BioMed Paper Radar data from RSS/Atom feeds.

Usage:
  pip install -r requirements.txt
  python scripts/update_feeds.py

Optional environment variables:
  MAX_ITEMS_PER_FEED=50
  ENABLE_TRANSLATION=false
  OPENAI_API_KEY=...
  OPENAI_MODEL=your-preferred-model
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any

import feedparser

ROOT = Path(__file__).resolve().parents[1]
FEEDS_PATH = ROOT / "config" / "feeds.json"
TAGS_PATH = ROOT / "config" / "tags.json"
DATA_PATH = ROOT / "data" / "articles.json"
TRENDS_PATH = ROOT / "data" / "trends.json"

MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "50"))
ENABLE_TRANSLATION = os.getenv("ENABLE_TRANSLATION", "false").lower() == "true"

AI_RELEVANCE_TERMS = [
    "artificial intelligence", "machine learning", "deep learning", "large language model",
    "llm", "foundation model", "transformer", "neural network", "generative", "diffusion",
    "self-supervised", "multimodal", "computer vision", "natural language processing",
    "causal inference", "federated learning", "graph neural network", "gnn"
]

BIO_RELEVANCE_TERMS = [
    "biomedical", "clinical", "medicine", "health", "epidemiology", "public health",
    "bioinformatics", "genomics", "single-cell", "transcriptomics", "proteomics",
    "drug discovery", "protein", "variant", "microbiome", "pathology", "radiology",
    "ehr", "electronic health record", "trial", "biomarker"
]

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(entry: Any) -> str:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = getattr(entry, key, None)
        if value:
            return dt.date(value.tm_year, value.tm_mon, value.tm_mday).isoformat()
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None)
        if value:
            parsed = feedparser._parse_date(value)
            if parsed:
                return dt.date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
    return dt.date.today().isoformat()


def get_authors(entry: Any) -> str:
    authors = getattr(entry, "authors", None)
    if authors:
        names = [a.get("name", "") for a in authors if isinstance(a, dict)]
        return ", ".join([n for n in names if n])
    return getattr(entry, "author", "") or ""


def find_doi(entry: Any, title: str, link: str, summary: str) -> str:
    for field in ("dc_identifier", "prism_doi", "doi"):
        value = getattr(entry, field, "")
        if value and "10." in str(value):
            match = DOI_RE.search(str(value))
            if match:
                return match.group(0)
    match = DOI_RE.search(" ".join([title, link, summary]))
    return match.group(0) if match else ""


def classify_tags(text: str, tag_config: dict[str, dict[str, list[str]]]) -> dict[str, list[str]]:
    text_l = text.lower()
    result = {}
    for group_name, mapping in tag_config.items():
        hits = []
        for tag, keywords in mapping.items():
            if any(k.lower() in text_l for k in keywords):
                hits.append(tag)
        result[group_name] = sorted(set(hits))
    result["tags"] = sorted(set(result.get("ai_tags", []) + result.get("bio_tags", []) + result.get("disease_tags", [])))
    return result


def is_relevant(text: str, tags: dict[str, list[str]], feed_group: str) -> bool:
    text_l = text.lower()
    ai_hit = any(t in text_l for t in AI_RELEVANCE_TERMS) or bool(tags.get("ai_tags"))
    bio_hit = any(t in text_l for t in BIO_RELEVANCE_TERMS) or bool(tags.get("bio_tags") or tags.get("disease_tags"))

    # Broad journals need both AI and BioMed signal. Narrow feeds can pass if either side is present.
    if "broad_filter_required" in feed_group:
        return ai_hit and bio_hit
    return ai_hit or bio_hit


def stable_id(article: dict[str, Any]) -> str:
    raw = article.get("doi") or article.get("url") or article.get("title", "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def maybe_translate(title: str, abstract: str) -> tuple[str, str]:
    # Kept intentionally optional. This avoids hard dependency on any vendor API.
    if not ENABLE_TRANSLATION:
        return "", ""

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "")
    if not api_key or not model:
        return "", ""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = (
            "请把下面的英文论文标题和摘要翻译成准确、简洁的中文。"
            "返回 JSON，字段为 title_zh 和 abstract_zh。\n\n"
            f"Title: {title}\nAbstract: {abstract}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return data.get("title_zh", ""), data.get("abstract_zh", "")
    except Exception as exc:
        print(f"[warn] translation skipped: {exc}")
        return "", ""


def fetch_feed(feed: dict[str, Any], tag_config: dict[str, Any]) -> list[dict[str, Any]]:
    print(f"[feed] {feed['name']} -> {feed['url']}")
    parsed = feedparser.parse(feed["url"])
    articles = []

    if getattr(parsed, "bozo", False):
        print(f"[warn] feed parse issue for {feed['name']}: {getattr(parsed, 'bozo_exception', '')}")

    for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
        title = strip_html(getattr(entry, "title", ""))
        summary = strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        link = getattr(entry, "link", "")
        text = f"{title}\n{summary}"
        classified = classify_tags(text, tag_config)

        if not is_relevant(text, classified, feed.get("group", "")):
            continue

        title_zh, abstract_zh = maybe_translate(title, summary)

        article = {
            "source_name": feed.get("name", ""),
            "journal": feed.get("journal", feed.get("name", "")),
            "title": title,
            "title_zh": title_zh,
            "abstract": summary,
            "abstract_zh": abstract_zh,
            "authors": get_authors(entry),
            "published_date": parse_date(entry),
            "updated_date": dt.date.today().isoformat(),
            "article_type": "Preprint" if feed.get("is_preprint") else "Article",
            "doi": find_doi(entry, title, link, summary),
            "url": link,
            "pdf_url": "",
            "tags": classified.get("tags", []),
            "ai_tags": classified.get("ai_tags", []),
            "bio_tags": classified.get("bio_tags", []),
            "disease_tags": classified.get("disease_tags", []),
            "is_preprint": 1 if feed.get("is_preprint") else 0,
        }
        article["id"] = stable_id(article)
        articles.append(article)

    return articles


def build_trends(articles: list[dict[str, Any]]) -> dict[str, Any]:
    by_tag: dict[str, int] = {}
    by_journal: dict[str, int] = {}
    by_month: dict[str, int] = {}

    for a in articles:
        journal = a.get("journal") or a.get("source_name") or "Unknown"
        by_journal[journal] = by_journal.get(journal, 0) + 1

        month = (a.get("published_date") or "")[:7] or "unknown"
        by_month[month] = by_month.get(month, 0) + 1

        for tag in a.get("tags", []):
            by_tag[tag] = by_tag.get(tag, 0) + 1

    return {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "by_tag": dict(sorted(by_tag.items(), key=lambda x: x[1], reverse=True)),
        "by_journal": dict(sorted(by_journal.items(), key=lambda x: x[1], reverse=True)),
        "by_month": dict(sorted(by_month.items())),
    }


def main() -> None:
    feed_config = load_json(FEEDS_PATH, {"feeds": []})
    tag_config = load_json(TAGS_PATH, {})
    old_data = load_json(DATA_PATH, {"articles": []})
    old_articles = old_data.get("articles", old_data if isinstance(old_data, list) else [])

    all_articles = list(old_articles)
    seen = {stable_id(a) for a in all_articles if a.get("title") or a.get("url") or a.get("doi")}

    for feed in feed_config.get("feeds", []):
        try:
            for article in fetch_feed(feed, tag_config):
                sid = stable_id(article)
                if sid not in seen:
                    all_articles.append(article)
                    seen.add(sid)
        except Exception as exc:
            print(f"[error] failed feed {feed.get('name')}: {exc}")

    all_articles.sort(key=lambda a: a.get("published_date", ""), reverse=True)

    DATA_PATH.write_text(
        json.dumps({"generated_at": dt.datetime.utcnow().isoformat() + "Z", "articles": all_articles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    TRENDS_PATH.write_text(json.dumps(build_trends(all_articles), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] articles={len(all_articles)} -> {DATA_PATH}")


if __name__ == "__main__":
    main()
