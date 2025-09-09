#!/usr/bin/env python3
# app/scrapers/html.py
"""
Shim to preserve legacy imports.

Background:
-----------
The main HTML scraper implementation was moved to `html_utils.py`.
However, some older code and tests may still do:

    from app.scrapers.html import run_html

This shim re-exports run_html from html_utils.py to avoid breaking imports.

Usage:
------
    from app.scrapers.html import run_html
    # Works exactly the same as:
    from app.scrapers.html_utils import run_html
"""

from .html_utils import run_html  # re-export

__all__ = ["run_html"]
