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
        content_parts.append(text)

    article_text = "\n\n".join(content_parts)

    article_text = "\n".join(line.strip() for line in article_text.splitlines() if line.strip())

    article_text = str({"article_text": article_text, "url": url})

    return article_text


@tool
def get_script_length(script: str) -> dict:
    """Get length of script in symbols and words."""
    print(f"Tool call: get_script_length({script})")
    return {"total_symbols": len(script), "total_words": len(script.split())}
