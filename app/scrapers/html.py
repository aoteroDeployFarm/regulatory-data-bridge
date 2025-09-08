# app/scrapers/html.py
"""
Shim to preserve old imports:
    from app.scrapers.html import run_html
after renaming the implementation to html_utils.py
"""
from .html_utils import run_html  # re-export
__all__ = ["run_html"]
