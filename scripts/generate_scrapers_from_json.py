#!/usr/bin/env python3
"""
generate_scrapers_from_json.py — Generate scraper modules from a simple JSON config.

Place at: tools/generate_scrapers_from_json.py
Run from the repo root (folder that contains app/).

What this does:
  - Reads a config file (JSON / NDJSON) describing target URLs (by state or arbitrary lists).
  - Normalizes entries and creates Python scraper modules under <outdir>/state/<code>/.
  - Emits either *_html_scraper.py or *_pdf_scraper.py based on the URL.
  - Creates lightweight, self-caching scrapers that:
      • For HTML: fetch page, extract text via BeautifulSoup (+ optional CSS selector)
      • For PDF: fetch bytes and extract text via pypdf or pdfminer.six
    Each scraper tracks a simple "signature" (ETag/Last-Modified/Content-Length or SHA) and a last content snapshot.

Accepted input formats (auto-detected):
  1) Dict of state → [urls]:         {"Colorado": ["https://...", ...], "AK": ["https://...", ...]}
  2) List of URL strings:            ["https://...", "https://..."]
  3) Nested dicts/lists with keys:   one of ["target_url","url","link","href","source_url","pdf_url","website"]
     (The script walks nested structures to find URLs.)

State detection:
  - If the dict form is used (state → [urls]), the key is used to infer jurisdiction code (e.g., "Colorado" → "co").
  - Otherwise, name/slug/id/title/state fields may influence the subdirectory, if recognizable.

Where files go:
  <outdir>/
    __init__.py
    state/
      __init__.py
      <code>/
        __init__.py
        <generated-name>_html_scraper.py
        <generated-name>_pdf_scraper.py
        .cache/ (created at runtime by each scraper)

Common examples:
  # 1) Dict of states → urls (default selector for HTML)
  python tools/generate_scrapers_from_json.py \
    --config state-website-data/state-website-data.json \
    --outdir scrapers \
    --default-selector "main, article, section, h1, h2, h3"

  # 2) Overwrite existing generated files
  python tools/generate_scrapers_from_json.py --config my.cfg.json --outdir scrapers --overwrite

  # 3) NDJSON list of objects with various url fields
  python tools/generate_scrapers_from_json.py --config sources.ndjson --outdir scrapers

Notes:
  - Filenames are derived from (name?, host, path) and uniqued within each state folder.
  - HTML scrapers default to selector "main, article, section, h1, h2, h3" (override with --default-selector).
  - PDF scrapers require either pypdf or pdfminer.six at runtime to extract text.
  - Exit codes: 0 success; 2 config read error; 3 no valid entries found.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

# -------------------------
# State mapping
# -------------------------

def _norm_state_key(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\bstate of\b", "", s)
    s = re.sub(r"[^a-z]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

STATE_TO_CODE: Dict[str, str] = {
    # 50 states + DC
    "alabama": "al", "al": "al",
    "alaska": "ak", "ak": "ak",
    "arizona": "az", "az": "az",
    "arkansas": "ar", "ar": "ar",
    "california": "ca", "ca": "ca",
    "colorado": "co", "co": "co",
    "connecticut": "ct", "ct": "ct",
    "delaware": "de", "de": "de",
    "florida": "fl", "fl": "fl",
    "georgia": "ga", "ga": "ga",
    "hawaii": "hi", "hi": "hi",
    "idaho": "id", "id": "id",
    "illinois": "il", "il": "il",
    "indiana": "in", "in": "in",
    "iowa": "ia", "ia": "ia",
    "kansas": "ks", "ks": "ks",
    "kentucky": "ky", "ky": "ky",
    "louisiana": "la", "la": "la",
    "maine": "me", "me": "me",
    "maryland": "md", "md": "md",
    "massachusetts": "ma", "ma": "ma",
    "michigan": "mi", "mi": "mi",
    "minnesota": "mn", "mn": "mn",
    "mississippi": "ms", "ms": "ms",
    "missouri": "mo", "mo": "mo",
    "montana": "mt", "mt": "mt",
    "nebraska": "ne", "ne": "ne",
    "nevada": "nv", "nv": "nv",
    "new hampshire": "nh", "nh": "nh",
    "new jersey": "nj", "nj": "nj",
    "new mexico": "nm", "nm": "nm",
    "new york": "ny", "ny": "ny",
    "north carolina": "nc", "nc": "nc",
    "north dakota": "nd", "nd": "nd",
    "ohio": "oh", "oh": "oh",
    "oklahoma": "ok", "ok": "ok",
    "oregon": "or", "or": "or",
    "pennsylvania": "pa", "pa": "pa",
    "rhode island": "ri", "ri": "ri",
    "south carolina": "sc", "sc": "sc",
    "south dakota": "sd", "sd": "sd",
    "tennessee": "tn", "tn": "tn",
    "texas": "tx", "tx": "tx",
    "utah": "ut", "ut": "ut",
    "vermont": "vt", "vt": "vt",
    "virginia": "va", "va": "va",
    "washington": "wa", "wa": "wa",
    "west virginia": "wv", "wv": "wv",
    "wisconsin": "wi", "wi": "wi",
    "wyoming": "wy", "wy": "wy",
    "district of columbia": "dc", "washington dc": "dc", "dc": "dc", "d c": "dc"
}

def state_code_for(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    key = _norm_state_key(name)
    return STATE_TO_CODE.get(key)

# -------------------------
# Helpers
# -------------------------

URL_KEYS = ["target_url", "url", "link", "href", "source_url", "pdf_url", "website"]

def read_json(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # Try NDJSON
        rows = []
        for line in txt.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
        if rows:
            return rows
        raise

def slugify(s: str, max_len: int = 50) -> str:
    s = s.strip().lower()
    s = re.sub(r"https?://", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "source"

def host_slug(u: str) -> str:
    try:
        h = urlparse(u).netloc.lower()
        h = re.sub(r"^www\.", "", h)
        return slugify(h, max_len=50)
    except Exception:
        return "host"

def path_slug(u: str) -> str:
    try:
        p = urlparse(u).path
        if not p or p == "/":
            return "root"
        parts = [seg for seg in p.split("/") if seg]
        parts = parts[:4]  # keep it short
        s = "-".join(slugify(seg, 20) for seg in parts if seg)
        return s or "root"
    except Exception:
        return "root"

def guess_type(u: str) -> str:
    return "pdf" if u.lower().split("?")[0].endswith(".pdf") else "html"

def iter_nodes(x: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from iter_nodes(v)
    elif isinstance(x, list):
        for v in x:
            yield from iter_nodes(v)

def pick_url(d: Dict[str, Any]) -> Optional[str]:
    for k in URL_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return v
    return None

def normalize_entries(raw: Any, default_selector: Optional[str]) -> List[Dict[str, Any]]:
    """
    Produce entries with:
      { name?: str, target_url: str, type?: 'html'|'pdf', selector?: str }
    Accepts:
      - dict of {state: [url, url, ...]}  <-- your file shape
      - list of strings (urls)
      - list/dicts with any of URL_KEYS
      - nested structures (recursively)
    """
    entries: List[Dict[str, Any]] = []

    # Case 1: dict of "state": [urls...]
    if isinstance(raw, dict):
        all_values_are_lists = all(isinstance(v, list) for v in raw.values())
        if all_values_are_lists:
            for state, urls in raw.items():
                if not isinstance(urls, list):
                    continue
                for u in urls:
                    if isinstance(u, str) and u.startswith(("http://", "https://")):
                        entries.append({
                            "name": state,
                            "target_url": u,
                            "type": guess_type(u),
                            "selector": default_selector if guess_type(u) == "html" else None,
                        })
        else:
            # Fall through to generic walker
            pass

    # Generic walker: catches lists, nested dicts, etc.
    for node in iter_nodes(raw):
        url = pick_url(node)
        if url:
            name = (node.get("name")
                    or node.get("slug")
                    or node.get("id")
                    or node.get("title")
                    or node.get("state")
                    or None)
            entries.append({
                "name": name,
                "target_url": url,
                "type": (node.get("type") or guess_type(url)).lower(),
                "selector": node.get("selector") or (default_selector if guess_type(url) == "html" else None),
            })
        # Also allow plain url strings tucked inside dicts
        for k, v in list(node.items()):
            if isinstance(v, str) and v.startswith(("http://", "https://")) and k not in URL_KEYS:
                entries.append({
                    "name": node.get("name") or node.get("slug") or node.get("id") or node.get("title") or None,
                    "target_url": v,
                    "type": guess_type(v),
                    "selector": default_selector if guess_type(v) == "html" else None,
                })

    # Also, if the top-level is a list of raw URL strings:
    if isinstance(raw, list):
        for v in raw:
            if isinstance(v, str) and v.startswith(("http://", "https://")):
                entries.append({
                    "name": None,
                    "target_url": v,
                    "type": guess_type(v),
                    "selector": default_selector if guess_type(v) == "html" else None,
                })

    # Filter + de-dup by target_url
    norm: List[Dict[str, Any]] = []
    seen = set()
    for e in entries:
        u = e.get("target_url")
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        t = (e.get("type") or guess_type(u)).lower()
        e["type"] = t if t in ("html", "pdf") else guess_type(u)
        if e["type"] == "html" and not e.get("selector"):
            e["selector"] = default_selector
        norm.append(e)

    return norm

def unique_filename(base: str, used: set[str]) -> str:
    """Ensure unique filename stem (without extension) within a directory."""
    b = base
    i = 2
    while b in used:
        b = f"{base}-{i}"
        i += 1
    used.add(b)
    return b

# -------------------------
# Templates
# -------------------------

HTML_TEMPLATE = """# Auto-generated by generate_scrapers_from_json.py (HTML)
from __future__ import annotations
from pathlib import Path
import hashlib, json
from typing import Optional

# HTTP client selection
try:
    import httpx
    _HTTPX = True
except Exception:  # pragma: no cover
    _HTTPX = False
    import requests

from bs4 import BeautifulSoup

TARGET_URL = "{target_url}"
from pathlib import Path

# Per-scraper cache directory:
# scrapers/state/<code>/.cache/<scraper_stem>/
CACHE_DIR = Path(__file__).parent / ".cache" / Path(__file__).stem
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SIGNATURE_FILE = CACHE_DIR / "last_signature.json"
CONTENT_FILE   = CACHE_DIR / "last_content.txt"


DEFAULT_SELECTOR = {default_selector!r}

def _head(url: str):
    if _HTTPX:
        with httpx.Client(timeout=15.0, follow_redirects=True) as c:
            r = c.head(url)
            r.raise_for_status()
            return r
    else:
        r = requests.head(url, allow_redirects=True, timeout=15)
        if r.status_code >= 400:
            r.raise_for_status()
        return r

def _get_text(url: str) -> str:
    if _HTTPX:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers={{"User-Agent": "RegDataBridge/1.0"}}) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text
    else:
        r = requests.get(url, timeout=30, headers={{"User-Agent": "RegDataBridge/1.0"}})
        r.raise_for_status()
        return r.text

def _extract_text(html: str, selector: Optional[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text_parts = []
    nodes = soup.select(selector) if selector else [soup]
    if not nodes:
        nodes = [soup]
    for n in nodes:
        for tag in n(["script", "style", "noscript", "nav", "header", "footer", "iframe"]):
            tag.decompose()
        t = n.get_text(separator="\\n", strip=True)
        if t:
            text_parts.append(t)
    return "\\n\\n".join(text_parts).strip()

def check_for_update(selector: Optional[str] = None) -> dict:
    selector = selector or DEFAULT_SELECTOR
    new_signature = ""
    html = ""
    try:
        head_r = _head(TARGET_URL)
        etag = head_r.headers.get("ETag", "")
        lm = head_r.headers.get("Last-Modified", "")
        cl = head_r.headers.get("Content-Length", "")
        if etag or lm or cl:
            new_signature = f"etag={{etag}}|lm={{lm}}|cl={{cl}}"
        else:
            html = _get_text(TARGET_URL)
            new_signature = f"sha256={{hashlib.sha256(html.encode('utf-8', 'ignore')).hexdigest()}}"
    except Exception as e:
        return {{
            "url": TARGET_URL,
            "updated": False,
            "diffSummary": f"Error getting signature: {{e}}",
            "error": str(e),
            "meta": {{"content_type": "html", "selector_used": selector, "signature": "", "fetched_at": None}},
        }}

    old_signature = ""
    old_content = ""
    if SIGNATURE_FILE.exists():
        try:
            cached = json.loads(SIGNATURE_FILE.read_text("utf-8"))
            old_signature = cached.get("signature", "")
        except Exception:
            pass
    if CONTENT_FILE.exists():
        try:
            old_content = CONTENT_FILE.read_text("utf-8")
        except Exception:
            old_content = ""

    is_updated = (new_signature != old_signature)

    if is_updated:
        if not html:
            try:
                html = _get_text(TARGET_URL)
            except Exception as e:
                return {{
                    "url": TARGET_URL,
                    "updated": False,
                    "diffSummary": f"Error downloading page: {{e}}",
                    "error": str(e),
                    "meta": {{"content_type": "html", "selector_used": selector, "signature": new_signature, "fetched_at": None}},
                }}
        try:
            new_content = _extract_text(html, selector)
        except Exception as e:
            return {{
                "url": TARGET_URL,
                "updated": False,
                "diffSummary": f"Error extracting HTML: {{e}}",
                "error": str(e),
                "meta": {{"content_type": "html", "selector_used": selector, "signature": new_signature, "fetched_at": None}},
            }}

        SIGNATURE_FILE.write_text(json.dumps({{"signature": new_signature}}), encoding="utf-8")
        CONTENT_FILE.write_text(new_content, encoding="utf-8")

        return {{
            "url": TARGET_URL,
            "updated": True,
            "diffSummary": "Content/signature changed",
            "new_content": new_content,
            "old_content": old_content,
            "meta": {{
                "content_type": "html",
                "selector_used": selector,
                "signature": new_signature,
                "fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            }},
        }}

    return {{
        "url": TARGET_URL,
        "updated": False,
        "diffSummary": "No change",
        "new_content": None,
        "old_content": old_content,
        "meta": {{
            "content_type": "html",
            "selector_used": selector,
            "signature": new_signature,
            "fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }},
    }}

if __name__ == "__main__":
    print(json.dumps(check_for_update(), indent=2))
"""

PDF_TEMPLATE = """# Auto-generated by generate_scrapers_from_json.py (PDF)
from __future__ import annotations
from pathlib import Path
import hashlib, json, io

# HTTP client selection
try:
    import httpx
    _HTTPX = True
except Exception:  # pragma: no cover
    _HTTPX = False
    import requests

try:
    import pypdf
except Exception:
    pypdf = None

try:
    from pdfminer_high_level import extract_text as pdfminer_extract_text  # type: ignore
except Exception:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore
    except Exception:
        pdfminer_extract_text = None

TARGET_URL = "{target_url}"
CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SIGNATURE_FILE = CACHE_DIR / "last_signature.json"
CONTENT_FILE = CACHE_DIR / "last_content.txt"

def _head(url: str):
    if _HTTPX:
        with httpx.Client(timeout=15.0, follow_redirects=True) as c:
            r = c.head(url)
            r.raise_for_status()
            return r
    else:
        r = requests.head(url, allow_redirects=True, timeout=15)
        if r.status_code >= 400:
            r.raise_for_status()
        return r

def _get_bytes(url: str) -> bytes:
    if _HTTPX:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers={{"User-Agent": "RegDataBridge/1.0"}}) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.content
    else:
        r = requests.get(url, timeout=30, headers={{"User-Agent": "RegDataBridge/1.0"}})
        r.raise_for_status()
        return r.content

def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    if pypdf:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        out = []
        for page in reader.pages:
            try:
                out.append(page.extract_text() or "")
            except Exception:
                continue
        return "\\n".join([s for s in out if s]).strip()
    if pdfminer_extract_text:
        return (pdfminer_extract_text(io.BytesIO(pdf_bytes)) or "").strip()
    raise RuntimeError("No PDF text extraction library found (install pypdf or pdfminer.six)")

def check_for_update() -> dict:
    new_signature = ""
    pdf_bytes = b""
    try:
        head_r = _head(TARGET_URL)
        etag = head_r.headers.get("ETag", "")
        lm = head_r.headers.get("Last-Modified", "")
        cl = head_r.headers.get("Content-Length", "")
        if etag or lm or cl:
            new_signature = f"etag={{etag}}|lm={{lm}}|cl={{cl}}"
        else:
            pdf_bytes = _get_bytes(TARGET_URL)
            new_signature = f"sha256={{hashlib.sha256(pdf_bytes).hexdigest()}}"
    except Exception as e:
        return {{
            "url": TARGET_URL,
            "updated": False,
            "diffSummary": f"Error getting PDF signature: {{e}}",
            "error": str(e),
            "meta": {{"content_type": "pdf", "selector_used": None, "signature": "", "fetched_at": None}},
        }}

    old_signature = ""
    old_content = ""
    if SIGNATURE_FILE.exists():
        try:
            cached = json.loads(SIGNATURE_FILE.read_text("utf-8"))
            old_signature = cached.get("signature", "")
        except Exception:
            pass
    if CONTENT_FILE.exists():
        try:
            old_content = CONTENT_FILE.read_text("utf-8")
        except Exception:
            old_content = ""

    is_updated = (new_signature != old_signature)

    if is_updated:
        if not pdf_bytes:
            try:
                pdf_bytes = _get_bytes(TARGET_URL)
            except Exception as e:
                return {{
                    "url": TARGET_URL,
                    "updated": False,
                    "diffSummary": f"Error downloading PDF: {{e}}",
                    "error": str(e),
                    "meta": {{"content_type": "pdf", "selector_used": None, "signature": new_signature, "fetched_at": None}},
                }}
        try:
            new_content = _extract_text_from_pdf_bytes(pdf_bytes)
        except Exception as e:
            return {{
                "url": TARGET_URL,
                "updated": False,
                "diffSummary": f"Error extracting text from PDF: {{e}}",
                "error": str(e),
                "meta": {{"content_type": "pdf", "selector_used": None, "signature": new_signature, "fetched_at": None}},
            }}

        SIGNATURE_FILE.write_text(json.dumps({{"signature": new_signature}}), encoding="utf-8")
        CONTENT_FILE.write_text(new_content, encoding="utf-8")

        return {{
            "url": TARGET_URL,
            "updated": True,
            "diffSummary": "PDF signature/content changed",
            "new_content": new_content,
            "old_content": old_content,
            "meta": {{
                "content_type": "pdf",
                "selector_used": None,
                "signature": new_signature,
                "fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            }},
        }}

    return {{
        "url": TARGET_URL,
        "updated": False,
        "diffSummary": "No change",
        "new_content": None,
        "old_content": old_content,
        "meta": {{
            "content_type": "pdf",
            "selector_used": None,
            "signature": new_signature,
            "fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }},
    }}

if __name__ == "__main__":
    print(json.dumps(check_for_update(), indent=2))
"""

# -------------------------
# Generation
# -------------------------

def filename_stem_for(entry: Dict[str, Any]) -> str:
    """Build a friendly filename stem without extension."""
    url = entry["target_url"]
    parts = []
    if entry.get("name"):
        parts.append(slugify(str(entry["name"]), 40))
    parts.append(host_slug(url))
    ps = path_slug(url)
    if ps != "root":
        parts.append(ps)
    stem = "-".join([p for p in parts if p]) or "source"
    return stem

def target_directory_for(entry: Dict[str, Any], base_outdir: Path) -> Path:
    """Return base_outdir/state/<code> or base_outdir/state/_unknown."""
    code = state_code_for(entry.get("name"))
    sub = code if code else "_unknown"
    d = base_outdir / "state" / sub
    d.mkdir(parents=True, exist_ok=True)
    # Ensure package markers (if you like to import scrapers.*)
    for mark in [base_outdir, base_outdir / "state", d]:
        initp = mark / "__init__.py"
        if not initp.exists():
            initp.write_text("# generated package marker\n", encoding="utf-8")
    return d

def render_template(entry: Dict[str, Any], default_selector: Optional[str]) -> str:
    t = entry["type"]
    if t == "pdf":
        return PDF_TEMPLATE.format(target_url=entry["target_url"])
    return HTML_TEMPLATE.format(
        target_url=entry["target_url"],
        default_selector=(entry.get("selector") or default_selector or "main, article, section, h1, h2, h3"),
    )

def main():
    ap = argparse.ArgumentParser(description="Generate scraper modules from a config file.")
    ap.add_argument("--config", required=True, help="Path to config JSON (dict of state→urls or list).")
    ap.add_argument("--outdir", required=True, help="Output root directory for scraper files.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    ap.add_argument("--default-selector", default="main, article, section, h1, h2, h3", help="Default CSS selector for HTML sources.")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    # top-level package marker
    init_path = outdir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("# generated package marker\n", encoding="utf-8")

    try:
        raw = read_json(cfg_path)
    except Exception as e:
        print(f"Failed to read config: {e}", file=sys.stderr)
        sys.exit(2)

    entries = normalize_entries(raw, args.default_selector)
    if not entries:
        print("No valid entries found in config (need at least one with target_url/url/etc.).", file=sys.stderr)
        sys.exit(3)

    # Track uniqueness per directory (so same stem can appear under different states)
    used_stems_per_dir: Dict[Path, set[str]] = {}
    written = 0

    for e in entries:
        dirpath = target_directory_for(e, outdir)
        used = used_stems_per_dir.setdefault(dirpath, set())
        stem = filename_stem_for(e)
        stem = unique_filename(stem, used)
        suffix = "_html_scraper.py" if e["type"] == "html" else "_pdf_scraper.py"
        path = dirpath / f"{stem}{suffix}"

        if path.exists() and not args.overwrite:
            print(f"Skip (exists): {path}")
            continue

        src = render_template(e, args.default_selector)
        path.write_text(src, encoding="utf-8")
        written += 1

    print(f"Generated {written} scraper(s) under {outdir.resolve()}/state/<code>/")

if __name__ == "__main__":
    main()
