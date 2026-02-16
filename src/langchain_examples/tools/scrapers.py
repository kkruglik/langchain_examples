import random
import time

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain_core.tools import tool

from langchain_examples.logging import get_logger

logger = get_logger(__name__)


@tool
def scrape_telegram_post(url: str) -> str:
    """Scrape content from Telegram post URL.

    Args:
        url: Telegram post URL (e.g., https://t.me/channel/123)

    Returns:
        Dict with article_text and url as a string, or error message if not a Telegram URL
    """
    logger.info("Tool call: scrape_telegram_post(%s)", url)

    if "t.me/" not in url:
        error_msg = f"Error: Not a Telegram URL. Expected format: https://t.me/channel/post_id. Got: {url}"
        logger.error(error_msg)
        return str({"error": error_msg, "url": url})

    if "/s/" not in url:
        url = url.replace("t.me/", "t.me/s/")
        logger.debug("Converted to embed URL: %s", url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Sec-GPC": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
        "TE": "trailers",
    }

    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30.0)
    soup = BeautifulSoup(r.text, "html.parser")

    message_div = soup.find("div", class_="tgme_widget_message_text")
    if message_div:
        article_text = message_div.get_text(strip=True)
    else:
        article_text = soup.get_text(strip=True)

    return str({"article_text": article_text, "url": url})



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


def _get_headers(url: str = "") -> dict:
    """Get randomized browser-like headers."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
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


def _random_delay():
    """Small random delay to mimic human behavior."""
    time.sleep(random.uniform(0.3, 1.2))


def _extract_content(soup: BeautifulSoup) -> str:
    """Extract article content preserving heading/paragraph order."""
    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "aside", "header", "noscript", "iframe", "form"]):
        tag.decompose()

    # Try <article> tag first
    article = soup.find("article")
    if article:
        container = article
    else:
        # Fallback to <main> or <body>
        container = soup.find("main") or soup.body or soup

    if not container:
        return ""

    # Walk DOM in order, extracting headings and paragraphs
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


@tool
def scrape_article(url: str) -> str:
    """Scrape article content from web page URL.

    Args:
        url: Web page URL to scrape

    Returns:
        Article text with source URL, or error message if failed
    """
    logger.info("Tool call: scrape_article(%s)", url)

    try:
        _random_delay()
        with httpx.Client(follow_redirects=True, timeout=30.0, cookies={}) as client:
            r = client.get(url, headers=_get_headers(url))
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        content = _extract_content(soup)
        if not content:
            return f"Error: Could not extract content from {url}"

        return f"Source: {url}\n\n{content}"

    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} for {url}"
    except httpx.RequestError as e:
        return f"Error: Request failed for {url}: {e}"
    except Exception as e:
        return f"Error: Failed to scrape {url}: {e}"


@tool
def analyze_script(script: str) -> dict:
    """Analyze script length and estimate speaking time.

    Args:
        script: The script text to analyze

    Returns:
        Dict with character count, word count, and estimated speaking time in seconds
    """
    logger.debug("Tool call: analyze_script")
    words = script.split()
    word_count = len(words)
    char_count = len(script)

    # Average speaking rate: 150 words per minute (2.5 words per second)
    speaking_time_seconds = int(word_count / 2.5)

    return {
        "characters": char_count,
        "words": word_count,
        "speaking_time_seconds": speaking_time_seconds,
        "speaking_time_formatted": f"{speaking_time_seconds // 60}:{speaking_time_seconds % 60:02d}",
    }


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default 5, max 10)

    Returns:
        Search results as formatted text
    """
    logger.info("Tool call: web_search(%s)", query)
    max_results = min(max_results, 10)

    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"No results found for: {query}"

        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n")
        return "\n---\n".join(formatted)

    except Exception as e:
        logger.error("web_search failed: %s", e)
        return f"Error: Search failed for '{query}'. Try a different query or continue without this search."


if __name__ == "__main__":
    from langchain_examples.logging import setup_logging

    setup_logging()

    # Test Telegram scraper with valid URL
    telegram_url = "https://t.me/svobodnieslova/7898"
    logger.info("Testing Telegram scraper with valid URL:")
    result = scrape_telegram_post(telegram_url)
    logger.info("Result: %s", result)

    # Test Telegram scraper with invalid URL
    logger.info("Testing Telegram scraper with invalid URL:")
    result = scrape_telegram_post("https://example.com/article")
    logger.info("Result: %s", result)
