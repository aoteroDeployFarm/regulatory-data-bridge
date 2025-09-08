#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================
#  Stdlib shadowing guard (must be FIRST)
#  Detect local files that mask Python's stdlib (e.g., html.py).
#  If found, fail fast with a clear message.
# ============================================================
if True:
    import importlib.util
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    SUSPECTS = [
        "html", "json", "logging", "asyncio", "email",
        "types", "typing", "re", "pathlib", "dataclasses",
    ]

    offenders = []

    # Where Python would import these from
    for name in SUSPECTS:
        try:
            spec = importlib.util.find_spec(name)
        except Exception:
            spec = None
        origin = getattr(spec, "origin", None) if spec else None
        if isinstance(origin, str):
            try:
                p = Path(origin).resolve()
            except Exception:
                continue
            if str(p).startswith(str(PROJECT_ROOT)):
                offenders.append((name, str(p)))

    # Also flag top-level <name>.py in the project root
    for name in SUSPECTS:
        f = PROJECT_ROOT / f"{name}.py"
        if f.exists():
            offenders.append((name, str(f.resolve())))

    if offenders:
        lines = ["Detected files that shadow Python stdlib modules. Rename/move these files:"]
        seen = set()
        for name, path in offenders:
            key = (name, path)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  - {name}: {path}")
        raise RuntimeError("\n".join(lines))

# ============================================================
#  App setup
# ============================================================
import os
import importlib
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html

APP_NAME = os.getenv("APP_NAME", "Regulatory Data Bridge")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Scrape and serve regulatory documents (HTML & PDF) with an Admin API.",
)

# ------------------------------------------------------------
# CORS (from env: CORS_ALLOWED_ORIGINS="http://127.0.0.1:5173,https://example.com")
# ------------------------------------------------------------
def _parse_origins(env_value: str | None) -> List[str]:
    if not env_value:
        return []
    return [o.strip() for o in env_value.split(",") if o.strip()]

CORS_ALLOWED_ORIGINS = _parse_origins(os.getenv("CORS_ALLOWED_ORIGINS"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS or ["*"],  # be strict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Include routers (auto-detect; ignore if a module is missing)
# We try: app.routers.sources, documents, alerts, admin, changes
# Each should expose a FastAPI APIRouter named `router`
# ------------------------------------------------------------
def _try_include(router_mod_name: str):
    try:
        mod = importlib.import_module(router_mod_name)
        router = getattr(mod, "router", None)
        if router is not None:
            app.include_router(router)
            return True
    except Exception:
        pass
    return False

for name in (
    "app.routers.sources",
    "app.routers.documents",
    "app.routers.alerts",
    "app.routers.admin",
    # NEW: mount the changes router if present
    "app.routers.changes",
):
    _try_include(name)

# ------------------------------------------------------------
# Health / readiness
# ------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs", status_code=302)

@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION}

@app.get("/ready", tags=["meta"])
def ready():
    # You can add lightweight DB checks here if desired.
    return {"ready": True}

# ============================================================
#  Custom Swagger UI with "Download CSV" button
#  Configure default via env CSV_DEFAULT_URL or edit below.
#  Tip: when /changes/export.csv is available, set:
#  CSV_DEFAULT_URL="/changes/export.csv?jurisdiction=CO&since=2025-09-01"
# ============================================================
CSV_DEFAULT_URL = os.getenv("CSV_DEFAULT_URL", "/documents/export.csv?jurisdiction=CO&limit=200")

@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html():
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>{app.title} – API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
    <style>
      body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Inter, Helvetica, Arial; }}
      #topbar {{ padding: 10px 14px; border-bottom: 1px solid #eee; display:flex; gap:10px; align-items:center; flex-wrap: wrap; }}
      .btn {{ cursor:pointer; padding:6px 12px; border-radius:6px; border:1px solid #dcdcdc; background:#f7f7f7; }}
      .btn:hover {{ background:#efefef; }}
      #swagger-ui {{ margin: 0 0 20px 0; }}
      input#csvUrl {{ min-width: 520px; padding:6px 10px; border:1px solid #dcdcdc; border-radius:6px; }}
      small.hint {{ opacity:.7 }}
    </style>
  </head>
  <body>
    <div id="topbar">
      <button class="btn" id="downloadCsvBtn">⬇️ Download CSV</button>
      <input id="csvUrl" value="{CSV_DEFAULT_URL}" />
      <small class="hint">Change the URL, then click the button.</small>
    </div>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({{
        url: "{app.openapi_url}",
        dom_id: "#swagger-ui",
        deepLinking: true,
        persistAuthorization: true
      }});
      document.getElementById("downloadCsvBtn").onclick = function() {{
        var path = document.getElementById("csvUrl").value || "{CSV_DEFAULT_URL}";
        var u = new URL(path, window.location.origin);
        window.open(u, "_blank");
      }};
    </script>
  </body>
</html>"""
    return HTMLResponse(html)

@app.get("/docs/oauth2-redirect", include_in_schema=False)
def swagger_ui_redirect():
    # keeps OAuth flows compatible if you add them later
    return get_swagger_ui_oauth2_redirect_html()
