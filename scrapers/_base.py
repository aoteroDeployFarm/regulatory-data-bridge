# scrapers/_base.py
import os, hashlib
from datetime import datetime
from bs4 import BeautifulSoup

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()

def extract_text(html: str, selector: str | None = None) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if selector:
        nodes = soup.select(selector)
        return "\n".join(n.get_text(strip=True) for n in nodes)
    return soup.get_text(" ", strip=True)

def check_updated(fetch_html_fn, cache_dir: str, selector: str | None = None, url: str = "", diff_label: str = "Content"):
    ensure_dir(cache_dir)
    cache_file = os.path.join(cache_dir, "last_hash.txt")

    html = fetch_html_fn()
    body = extract_text(html, selector=selector)
    new_hash = content_hash(body)

    old_hash = None
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            old_hash = f.read().strip()

    updated = (old_hash != new_hash)
    if updated:
        with open(cache_file, "w") as f:
            f.write(new_hash)

    return {
        "url": url,
        "updated": updated,
        "lastChecked": datetime.utcnow().isoformat() + "Z",
        "diffSummary": f"{diff_label} hash changed" if updated else "No change",
    }
