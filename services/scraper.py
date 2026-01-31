"""Web scraper for pineurs.com X-HEC guide content."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.pineurs.com"
DATA_DIR = Path(__file__).parent.parent / "data"
CONTEXT_FILE = DATA_DIR / "master_context.json"
LAST_SCRAPE_FILE = DATA_DIR / "last_scrape.txt"

# Pages to scrape
PAGES = {
    "program": "/en/program",
    "apply": "/en/apply",
    "resources": "/en/resources",
    "is_it_for_you": "/en/is-it-for-you",
    "home": "/en"
}


def scrape_page(url: str) -> Optional[str]:
    """
    Scrape content from a single page.
    
    Args:
        url: Full URL to scrape
        
    Returns:
        Extracted text content or None if failed
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Get main content
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        
        if main_content:
            # Extract text with some structure
            text_parts = []
            for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li']):
                text = element.get_text(strip=True)
                if text:
                    if element.name in ['h1', 'h2', 'h3', 'h4']:
                        text_parts.append(f"\n## {text}\n")
                    else:
                        text_parts.append(text)
            
            return "\n".join(text_parts)
        
        return soup.get_text(separator='\n', strip=True)
        
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def scrape_pineurs() -> dict:
    """
    Scrape all relevant pages from pineurs.com.
    
    Returns:
        Dictionary with scraped content organized by section
    """
    content = {
        "source": "pineurs.com",
        "scraped_at": datetime.now().isoformat(),
        "sections": {}
    }
    
    for section_name, path in PAGES.items():
        url = f"{BASE_URL}{path}"
        print(f"Scraping {section_name} from {url}...")
        
        page_content = scrape_page(url)
        if page_content:
            content["sections"][section_name] = {
                "url": url,
                "content": page_content
            }
    
    return content


def save_context(content: dict):
    """Save scraped content to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    
    with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    
    with open(LAST_SCRAPE_FILE, 'w') as f:
        f.write(datetime.now().isoformat())


def load_context() -> dict:
    """Load cached context from JSON file."""
    if CONTEXT_FILE.exists():
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_last_scrape_date() -> Optional[datetime]:
    """Get the date of the last scrape."""
    if LAST_SCRAPE_FILE.exists():
        with open(LAST_SCRAPE_FILE, 'r') as f:
            date_str = f.read().strip()
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                return None
    return None


def needs_rescrape() -> bool:
    """Check if we need to rescrape (more than 1 year old)."""
    last_scrape = get_last_scrape_date()
    if not last_scrape:
        return True
    
    days_since = (datetime.now() - last_scrape).days
    return days_since > 365


def get_master_context_text() -> str:
    """
    Get the master context as a formatted text string for the AI prompt.
    
    Returns:
        Formatted context string
    """
    context = load_context()
    
    if not context or not context.get("sections"):
        return "Contexte du Master X-HEC non disponible. Veuillez lancer un scrape."
    
    parts = ["# Informations sur le Master X-HEC Entrepreneurs\n"]
    parts.append(f"Source: {context.get('source', 'pineurs.com')}")
    parts.append(f"Dernière mise à jour: {context.get('scraped_at', 'inconnue')}\n")
    
    for section_name, section_data in context.get("sections", {}).items():
        section_title = section_name.replace("_", " ").title()
        parts.append(f"\n### {section_title}")
        parts.append(section_data.get("content", ""))
    
    return "\n".join(parts)


def update_context_if_needed() -> bool:
    """
    Check if context needs updating and update if necessary.
    
    Returns:
        True if context was updated, False otherwise
    """
    if needs_rescrape():
        print("Context needs updating, scraping pineurs.com...")
        content = scrape_pineurs()
        save_context(content)
        print("Context updated successfully!")
        return True
    return False


def force_rescrape() -> dict:
    """Force a rescrape regardless of last scrape date."""
    print("Forcing rescrape of pineurs.com...")
    content = scrape_pineurs()
    save_context(content)
    print("Rescrape completed!")
    return content
