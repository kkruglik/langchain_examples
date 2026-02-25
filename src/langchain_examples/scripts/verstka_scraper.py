import argparse
import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
]

REFERERS = [
    "https://www.google.com/",
    "https://www.google.com/search?q=news",
    "https://news.google.com/",
    "https://t.co/",
    "https://www.facebook.com/",
]

CATEGORIES = {
    "news": {
        "listing_url": "https://verstka.media/category/news",
        "page_pattern": "https://verstka.media/category/news/page/{n}",
        "output_file": "news.jsonl",
        "max_pages_default": 200,
    },
    "article": {
        "listing_url": "https://verstka.media/category/article",
        "page_pattern": "https://verstka.media/category/article/page/{n}",
        "output_file": "articles.jsonl",
        "max_pages_default": 60,
    },
}

DELAY_MIN = 1.0
DELAY_MAX = 2.5

BASE_URL = "https://verstka.media"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def load_seen_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def save_seen_url(path: Path, url: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(url + "\n")


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": random.choice(REFERERS),
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


def _polite_delay() -> None:
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def _fetch(client: httpx.Client, url: str) -> tuple[BeautifulSoup, str] | tuple[None, None]:
    """Returns (soup, final_url) or (None, None) on failure."""
    try:
        _polite_delay()
        r = client.get(url, headers=_get_headers())
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser"), str(r.url)
    except httpx.HTTPStatusError as e:
        logger.warning("HTTP %s for %s", e.response.status_code, url)
        return None, None
    except httpx.RequestError as e:
        logger.error("Request error for %s: %s", url, e)
        return None, None
    except Exception as e:
        logger.error("Unexpected error fetching %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Listing page parsing
# ---------------------------------------------------------------------------


def _is_article_url(url: str) -> bool:
    """True for slug-based article URLs, false for nav/category/tag/etc."""
    skip = ("/category/", "/page/", "/tag/", "/author/", "/topics", "/?", "#", "mailto:")
    path = url[len(BASE_URL) :] if url.startswith(BASE_URL) else url
    return bool(path) and path != "/" and not any(p in path for p in skip)


def parse_listing_page(soup: BeautifulSoup) -> list[dict]:
    # Verstka uses two listing layouts depending on category:
    #   news:    <li class="vm-news-list-item"> inside <ul class="vm-news-list">
    #   article: <li class="wp-block-post">     inside <ul class="wp-block-post-template">
    cards = soup.find_all("li", class_="vm-news-list-item")
    if not cards:
        cards = soup.find_all("li", class_="wp-block-post")

    results = []
    seen_urls: set[str] = set()

    if cards:
        for card in cards:
            time_tag = card.find("time")
            date_preview = time_tag.get("datetime", "") if time_tag else ""

            article_url = None
            for a in card.find_all("a", href=True):
                href = a["href"]
                url = href if href.startswith("http") else BASE_URL + href
                if url.startswith(BASE_URL) and _is_article_url(url) and url not in seen_urls:
                    article_url = url
                    break

            if not article_url:
                continue

            heading = card.find(["h1", "h2", "h3", "h4"])
            title = heading.get_text(strip=True) if heading else ""

            seen_urls.add(article_url)
            results.append({"url": article_url, "title": title, "date_preview": date_preview})
    else:
        # Nuclear fallback: collect all unique internal slug-based links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            url = href if href.startswith("http") else BASE_URL + href
            if not url.startswith(BASE_URL) or not _is_article_url(url) or url in seen_urls:
                continue
            title = a_tag.get_text(strip=True)
            if not title:
                continue
            seen_urls.add(url)
            results.append({"url": url, "title": title, "date_preview": ""})

    return results


def get_last_page(soup: BeautifulSoup) -> int:
    """Extract last page number from WordPress pagination."""
    nums = []
    for a in soup.select("a.page-numbers"):
        try:
            nums.append(int(a.get_text(strip=True)))
        except ValueError:
            pass
    return max(nums) if nums else 1


def get_article_urls(client: httpx.Client, category: str, seen_urls: set[str]) -> list[dict]:
    cfg = CATEGORIES[category]
    stubs = []

    soup, _ = _fetch(client, cfg["listing_url"])
    if soup is None:
        logger.warning("Failed to fetch first listing page for %s", category)
        return stubs

    last_page = get_last_page(soup)
    logger.info("Category=%s last_page=%d", category, last_page)

    for page in range(1, last_page + 1):
        if page == 1:
            page_soup = soup
        else:
            page_soup, _ = _fetch(client, cfg["page_pattern"].format(n=page))
            if page_soup is None:
                logger.warning("Failed to fetch listing page %s, skipping", page)
                continue

        page_stubs = parse_listing_page(page_soup)
        new_stubs = [s for s in page_stubs if s["url"] not in seen_urls]
        stubs.extend(new_stubs)
        logger.info("Page %s/%s: %d total, %d new", page, last_page, len(page_stubs), len(new_stubs))

    return stubs


# ---------------------------------------------------------------------------
# Article page parsing
# ---------------------------------------------------------------------------


def extract_json_ld(soup: BeautifulSoup) -> dict:
    target_types = {"NewsArticle", "Article", "BlogPosting"}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle @graph array
        if isinstance(data, dict) and "@graph" in data:
            candidates = data["@graph"]
        elif isinstance(data, list):
            candidates = data
        else:
            candidates = [data]

        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            obj_type = obj.get("@type", "")
            if isinstance(obj_type, list):
                match = any(t in target_types for t in obj_type)
            else:
                match = obj_type in target_types
            if not match:
                continue

            # Extract metadata
            result = {}

            headline = obj.get("headline") or obj.get("name")
            if headline:
                result["title"] = str(headline).strip()

            date_pub = obj.get("datePublished")
            if date_pub:
                result["date"] = str(date_pub)[:10]  # YYYY-MM-DD

            author = obj.get("author")
            if isinstance(author, dict):
                result["author"] = author.get("name", "")
            elif isinstance(author, list) and author:
                result["author"] = author[0].get("name", "") if isinstance(author[0], dict) else str(author[0])
            elif isinstance(author, str):
                result["author"] = author

            keywords = obj.get("keywords")
            if isinstance(keywords, list):
                result["tags"] = [str(k).strip() for k in keywords if k]
            elif isinstance(keywords, str) and keywords:
                result["tags"] = [k.strip() for k in keywords.split(",") if k.strip()]

            return result

    return {}


def extract_article_content(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "aside", "header", "noscript", "iframe", "form"]):
        tag.decompose()

    article = soup.find("article")
    if article:
        container = article
    else:
        container = soup.find("main") or soup.body or soup

    if not container:
        return ""

    parts = []
    for el in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"]):
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 10:
            continue
        if el.name.startswith("h"):
            level = int(el.name[1])
            parts.append(f"\n{'#' * level} {text}\n")
        else:
            parts.append(text)

    return "\n\n".join(parts)


def parse_article_page(soup: BeautifulSoup, url: str, category: str) -> dict | None:
    meta = extract_json_ld(soup)

    # HTML fallbacks for missing fields
    if not meta.get("title"):
        h1 = soup.find("h1")
        if h1:
            meta["title"] = h1.get_text(strip=True)

    if not meta.get("date"):
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            meta["date"] = str(time_tag["datetime"])[:10]

    if not meta.get("author"):
        author_el = soup.find(class_=lambda c: c and "author" in c.lower())
        if author_el:
            meta["author"] = author_el.get_text(strip=True)

    if not meta.get("tags"):
        tag_links = soup.find_all("a", rel="tag")
        if tag_links:
            meta["tags"] = [a.get_text(strip=True) for a in tag_links]

    content = extract_article_content(soup)
    if not content:
        logger.warning("Empty content for %s", url)
        return None

    return {
        "url": url,
        "title": meta.get("title", "").replace("\u00a0", " ").strip(),
        "date": meta.get("date", ""),
        "category": category,
        "author": meta.get("author", ""),
        "tags": meta.get("tags", []),
        "content": content,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _scrape_one(url: str, category: str) -> dict | None:
    """Fetch and parse a single article. Each call uses its own httpx client (thread-safe)."""
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        soup, _ = _fetch(client, url)
    if soup is None:
        return None
    return parse_article_page(soup, url, category)


def scrape_category(category: str, incremental: bool, data_dir: Path, workers: int = 5) -> int:
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = CATEGORIES[category]
    seen_path = data_dir / f"seen_urls_{category}.txt"
    out_path = data_dir / cfg["output_file"]

    seen_urls = load_seen_urls(seen_path) if incremental else set()
    logger.info("Category=%s incremental=%s seen=%d", category, incremental, len(seen_urls))

    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        stubs = get_article_urls(client, category, seen_urls)

    logger.info("Found %d new article(s) to scrape for category=%s", len(stubs), category)
    if not stubs:
        logger.info("Nothing new to scrape for category=%s", category)
        return 0

    scraped_count = 0
    error_count = 0
    write_lock = threading.Lock()

    with out_path.open("a", encoding="utf-8") as out_file:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_scrape_one, s["url"], category): s["url"] for s in stubs}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    record = future.result()
                except Exception as e:
                    logger.error("Unexpected error scraping %s: %s", url, e)
                    error_count += 1
                    save_seen_url(seen_path, url)
                    continue

                if record is None:
                    logger.warning("No content for %s, marking seen", url)
                    error_count += 1
                    save_seen_url(seen_path, url)
                    continue

                logger.info("Scraped: %s", url)
                with write_lock:
                    out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_file.flush()
                    save_seen_url(seen_path, url)
                scraped_count += 1

    logger.info("Category=%s done: scraped=%d errors=%d", category, scraped_count, error_count)
    return scraped_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Verstka.media scraper for RAG ingestion")
    parser.add_argument(
        "--category",
        choices=["news", "article", "all"],
        default="all",
        help="Which category to scrape (default: all)",
    )
    parser.add_argument(
        "--no-incremental",
        action="store_true",
        help="Disable incremental mode and re-scrape everything",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/verstka"),
        help="Output directory (default: data/verstka)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=7,
        help="Parallel article fetch workers (default: 7)",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    incremental = not args.no_incremental

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(data_dir / "scraper.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    categories = list(CATEGORIES.keys()) if args.category == "all" else [args.category]
    total = 0
    for cat in categories:
        total += scrape_category(cat, incremental, data_dir, workers=args.workers)

    logger.info("All done. Total articles scraped: %d", total)


if __name__ == "__main__":
    main()
