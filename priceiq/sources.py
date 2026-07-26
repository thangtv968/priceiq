"""Competitor sources: scrape product listings (name + price).

Two fetchers demonstrate two techniques:
  - books_toscrape : static HTML via requests + BeautifulSoup.
  - web_scraping_dev: headless browser via Playwright (JS-capable path).
Each returns a list[Listing]; the analysis layer is source-agnostic.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PriceIQ/0.1; +https://github.com/)"}


@dataclass
class Listing:
    competitor: str
    name: str
    price: Optional[float]
    currency: str
    url: str


def _num(text: str) -> Optional[float]:
    m = re.search(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))
    return float(m.group()) if m else None


def fetch_books_toscrape(competitor: str, base_url: str, max_pages: int = 3, delay: float = 0.5) -> list[Listing]:
    """Static scrape (requests + BeautifulSoup)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    listings: list[Listing] = []
    url: Optional[str] = urljoin(base_url, "catalogue/page-1.html")
    page = 1
    while url and page <= max_pages:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        for card in soup.select("article.product_pod"):
            a = card.select_one("h3 a")
            price_el = card.select_one("p.price_color")
            if not a or not price_el:
                continue
            listings.append(Listing(competitor, a["title"].strip(),
                                    _num(price_el.get_text()), "GBP",
                                    urljoin(url, a["href"])))
        nxt = soup.select_one("li.next a")
        url = urljoin(url, nxt["href"]) if nxt else None
        page += 1
        time.sleep(delay)
    return listings


def fetch_web_scraping_dev(competitor: str, base_url: str, max_pages: int = 3, delay: float = 0.5) -> list[Listing]:
    """JS-capable scrape via Playwright (headless Chromium) — shows browser rendering."""
    from playwright.sync_api import sync_playwright

    listings: list[Listing] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            pg = browser.new_page(user_agent=HEADERS["User-Agent"])
            for page in range(1, max_pages + 1):
                sep = "&" if "?" in base_url else "?"
                pg.goto(f"{base_url}{sep}page={page}", wait_until="domcontentloaded", timeout=30000)
                cards = pg.query_selector_all("div.row.product")
                if not cards:
                    break
                for card in cards:
                    a = card.query_selector("h3 a")
                    price_el = card.query_selector("div.price")
                    if not a or not price_el:
                        continue
                    listings.append(Listing(competitor, a.inner_text().strip(),
                                            _num(price_el.inner_text()), "USD",
                                            a.get_attribute("href")))
                time.sleep(delay)
        finally:
            browser.close()
    return listings


FETCHERS = {
    "books_toscrape": fetch_books_toscrape,
    "web_scraping_dev": fetch_web_scraping_dev,
}


def scrape_competitor(comp: dict) -> list[Listing]:
    """Dispatch by competitor 'type'. Never raises for empty results, only for misconfig."""
    fetcher = FETCHERS.get(comp.get("type"))
    if fetcher is None:
        raise ValueError(f"unknown competitor type {comp.get('type')!r} "
                         f"(known: {list(FETCHERS)})")
    return fetcher(comp["name"], comp["url"], comp.get("max_pages", 3))
