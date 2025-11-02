import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool


@tool
def scrape_article(url: str) -> str:
    """Scrape article content from URL, extracting only meaningful text."""
    print(f"Tool call: scrape_article({url})")
    r = httpx.get(url, follow_redirects=True)
    soup = BeautifulSoup(r.text, "html.parser")

    for script in soup(["script", "style", "nav", "footer", "aside", "header"]):
        script.decompose()

    content_parts = []

    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = heading.get_text(strip=True)
        if text:
            content_parts.append(f"\n## {text}\n")

    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(strip=True)
        if text and len(text) > 20:  # Filter out very short paragraphs
            content_parts.append(text)

    article_text = "\n\n".join(content_parts)

    article_text = "\n".join(line.strip() for line in article_text.splitlines() if line.strip())

    return article_text if article_text else soup.get_text(strip=True)
