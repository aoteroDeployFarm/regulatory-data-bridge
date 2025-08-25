import requests, os
from scrapers._base import check_updated
from bs4 import BeautifulSoup
import hashlib
import os
from datetime import datetime

TARGET_URL = "https://www.ferc.gov/news-events/news"
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "last_hash.txt")

def fetch_html():
    r = requests.get(TARGET_URL, timeout=15)
    r.raise_for_status()
    return r.text

def extract_content(html):
    soup = BeautifulSoup(html, "html.parser")
    main_section = soup.find("div", class_="view-news")
    return main_section.get_text(strip=True) if main_section else soup.get_text()

def compute_hash(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def load_last_hash():
    if not os.path.exists(CACHE_FILE):
        return None
    with open(CACHE_FILE, "r") as f:
        return f.read().strip()

def save_hash(new_hash):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        f.write(new_hash)

def check_for_update():
    html = fetch_html()
    content = extract_content(html)
    new_hash = compute_hash(content)
    old_hash = load_last_hash()

    updated = new_hash != old_hash
    if updated:
        save_hash(new_hash)

    return check_updated(
        fetch_html_fn=fetch_html,
        cache_dir=CACHE_DIR,
        selector=".view-content .views-row a, h2, h3",
        url=TARGET_URL,
        diff_label="FERC news"
    )

if __name__ == "__main__":
    print(check_for_update())
