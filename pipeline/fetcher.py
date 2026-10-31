import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import re
import yaml
from html import unescape
from typing import List, Dict, Any
from pathlib import Path
from .config import SOURCES_FILE
from .db import is_url_processed, record_fetched_article

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (ShirpalaBot/1.0)"

def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape HTML entities."""
    if not raw_html:
        return ""
    clean_re = re.compile('<.*?>')
    text = re.sub(clean_re, ' ', raw_html)
    text = unescape(text)
    return " ".join(text.split())

def load_sources(file_path: Path = SOURCES_FILE) -> List[Dict[str, Any]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Sources configuration file not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("sources", [])

def fetch_feed_xml(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")

def parse_feed(xml_text: str, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"[Fetcher] Failed to parse XML from {source['name']}: {e}")
        return items

    # Namespace handling for Atom or Content encoded
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'content': 'http://purl.org/rss/1.0/modules/content/'}

    # Case 1: RSS 2.0 (channel -> item)
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_elem = item.find("pubDate")
            content_elem = item.find("content:encoded", ns)

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""
            
            raw_content = ""
            if content_elem is not None and content_elem.text:
                raw_content = content_elem.text
            elif desc_elem is not None and desc_elem.text:
                raw_content = desc_elem.text

            summary = clean_html(raw_content)[:1200]

            if link and title:
                items.append({
                    "url": link,
                    "title": title,
                    "summary": summary,
                    "published": pub_date,
                    "source_name": source["name"],
                    "source_category": source.get("category", "Technology"),
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

        summary = clean_html(raw_content)[:1200]
        pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

        if link and title:
            items.append({
                "url": link,
                "title": title,
                "summary": summary,
                "published": pub_date,
                "source_name": source["name"],
                "source_category": source.get("category", "Technology"),
                "default_tags": source.get("default_tags", [])
            })

    return items

def fetch_new_articles(limit_per_source: int = 5) -> List[Dict[str, Any]]:
    """Fetch all enabled feeds and return only unread/unprocessed articles."""
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

            print(f"[Fetcher] Found {source_count} new articles from {source['name']}")
        except Exception as e:
            print(f"[Fetcher] Error fetching {source['name']}: {e}")

    return new_articles
