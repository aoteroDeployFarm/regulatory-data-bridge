import requests
from bs4 import BeautifulSoup
import hashlib
import os
from datetime import datetime

TARGET_URL = "https://www.conservation.ca.gov/calgem"
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "last_hash.txt")

def fetch_html():
    response = requests.get(TARGET_URL, timeout=10)
    response.raise_for_status()
    return response.text

def extract_content(html):
    soup = BeautifulSoup(html, "html.parser")
    main_content = soup.find("div", class_="sf_colsOut")  # Common on CA Gov sites
    return main_content.get_text(strip=True) if main_content else soup.get_text()

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

    return {
        "url": TARGET_URL,
        "updated": updated,
        "lastChecked": datetime.utcnow().isoformat() + "Z",
        "diffSummary": "CalGEM homepage content changed" if updated else "No change detected"
    }

if __name__ == "__main__":
    print(check_for_update())
