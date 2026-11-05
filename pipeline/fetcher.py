import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import re
import yaml
from html import unescape
from typing import List, Dict, Any, Tuple
from pathlib import Path
from .config import SOURCES_FILE
from .db import is_url_processed, record_fetched_article

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Low-value or noise patterns to filter out
DISALLOWED_TITLE_PATTERNS = [
    r'^\[\$\].*',                                       # Paywalled teasers (e.g. LWN [$])
    r'security updates for (monday|tuesday|wednesday|thursday|friday|saturday|sunday)',  # Package lists
    r'weekly digest\b',                                  # General digests
    r'meeting minutes\b',                                # Agenda/minutes notes
    r'biweekly update\b',
    r'happy (holidays|new year)',                        # Holiday greetings
]

def clean_html(raw_html: str) -> str:
    """Strip HTML tags, scripts, and normalize entities."""
    if not raw_html:
        return ""
    # Strip script and style blocks first
    cleaned = re.sub(r'<(script|style|svg|pre\s+class="[^"]*hidden")[^>]*>[\s\S]*?</\1>', ' ', raw_html, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = unescape(cleaned)
    return " ".join(cleaned.split())

def extract_main_article(url: str, timeout: int = 8) -> str:
    """Scrape and extract article body from a webpage if feed summary is too brief."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            # Strip non-content blocks
            html = re.sub(r'<(script|style|nav|footer|header|aside|noscript)[^>]*>[\s\S]*?</\1>', ' ', html, flags=re.IGNORECASE)
            
            # Look for semantic article containers
            article_match = re.search(r'<(?:article|main)[^>]*>([\s\S]*?)</(?:article|main)>', html, re.IGNORECASE)
            target = article_match.group(1) if article_match else html

            clean_text = clean_html(target)
            return clean_text[:6500]
    except Exception:
        return ""

def is_high_signal_article(title: str, summary: str) -> Tuple[bool, str]:
    """Validate that the candidate article is informative, relevant, and not low-value noise."""
    title_lower = title.strip().lower()

    for pat in DISALLOWED_TITLE_PATTERNS:
        if re.search(pat, title_lower):
            return False, f"Matches noise pattern: '{pat}'"

    if len(title.strip()) < 8:
        return False, "Title is too short"

    if len(summary.strip()) < 200:
        return False, f"Summary too brief ({len(summary.strip())} chars; need >= 200 for technical depth)"

    return True, "OK"

def load_sources(file_path: Path = SOURCES_FILE) -> List[Dict[str, Any]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Sources configuration file not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("sources", [])

def fetch_feed_xml(url: str, timeout: int = 15) -> str:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"
        }
    )
    with opener.open(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")

def parse_feed(xml_text: str, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"[Fetcher] Failed to parse XML from {source['name']}: {e}")
        return items

    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'content': 'http://purl.org/rss/1.0/modules/content/'
    }

    # Case 1: RSS 2.0 (channel -> item)
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_elem = item.find("pubDate")
            content_elem = item.find("content:encoded", ns) or item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

            # Prioritize full content over brief description
            raw_content = ""
            if content_elem is not None and content_elem.text:
                raw_content = content_elem.text
            elif desc_elem is not None and desc_elem.text:
                raw_content = desc_elem.text

            summary = clean_html(raw_content)[:6500]

            # If RSS gave only a short teaser, enrich from actual page
            if len(summary) < 600 and link:
                web_body = extract_main_article(link)
                if len(web_body) > len(summary):
                    summary = web_body

            if link and title:
                is_valid, reason = is_high_signal_article(title, summary)
                if not is_valid:
                    # Skip low-signal article
                    continue

                items.append({
                    "url": link,
                    "title": title,
                    "summary": summary,
                    "published": pub_date,
                    "source_name": source["name"],
                    "source_category": source.get("category", "تکنولوژی و دواپس"),
                    "default_tags": source.get("default_tags", [])
                })
        return items

    # Case 2: Atom (entry)
    entries = root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")
    for entry in entries:
        title_elem = entry.find("{http://www.w3.org/2005/Atom}title") or entry.find("title")
        link_elem = entry.find("{http://www.w3.org/2005/Atom}link") or entry.find("link")
        summary_elem = entry.find("{http://www.w3.org/2005/Atom}summary") or entry.find("summary")
        content_elem = entry.find("{http://www.w3.org/2005/Atom}content") or entry.find("content")
        pub_elem = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("published") or entry.find("updated")

        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        link = ""
        if link_elem is not None:
            link = link_elem.get("href", "") or (link_elem.text.strip() if link_elem.text else "")

        raw_content = ""
        if content_elem is not None and content_elem.text:
            raw_content = content_elem.text
        elif summary_elem is not None and summary_elem.text:
            raw_content = summary_elem.text

        summary = clean_html(raw_content)[:6500]

        # Enrich if too brief
        if len(summary) < 600 and link:
            web_body = extract_main_article(link)
            if len(web_body) > len(summary):
                summary = web_body

        pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

        if link and title:
            is_valid, reason = is_high_signal_article(title, summary)
            if not is_valid:
                continue

            items.append({
                "url": link,
                "title": title,
                "summary": summary,
                "published": pub_date,
                "source_name": source["name"],
                "source_category": source.get("category", "تکنولوژی و دواپس"),
                "default_tags": source.get("default_tags", [])
            })

    return items

def fetch_new_articles(limit_per_source: int = 3) -> List[Dict[str, Any]]:
    """Fetch high-signal candidate articles from curated engineering sources."""
    sources = load_sources()
    new_articles = []

    for source in sources:
        if not source.get("enabled", True):
            continue
        print(f"[Fetcher] Checking {source['name']} ({source['url']})...")
        try:
            xml_text = fetch_feed_xml(source["url"])
            parsed_items = parse_feed(xml_text, source)

            source_count = 0
            for item in parsed_items:
                if is_url_processed(item["url"]):
                    continue

                # Save into database as fetched
                article_id = record_fetched_article(
                    url=item["url"],
                    source_name=item["source_name"],
                    original_title=item["title"],
                    original_summary=item["summary"],
                    original_published=item["published"]
                )
                item["article_id"] = article_id
                new_articles.append(item)
                source_count += 1
                if source_count >= limit_per_source:
                    break

            print(f"[Fetcher] Found {source_count} high-quality candidate(s) from {source['name']}")
        except Exception as e:
            print(f"[Fetcher] Error fetching {source['name']}: {e}")

    return new_articles
