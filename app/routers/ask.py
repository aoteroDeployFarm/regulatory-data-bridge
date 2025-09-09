#!/usr/bin/env python3
"""
ask.py — FastAPI routes for retrieval-augmented Q&A.

Place at: app/routers/ask.py
Mount via: FastAPI(include_router(ask.router)).

What this does:
  - POST /ask
      Accepts a natural-language question + optional filters.
      Returns an AI-generated answer with citations (RAG).

Why it matters:
  - This is the primary endpoint for interactive Q&A.
  - Downstream clients (UI, chatbots) will call this route.
  - Currently returns a placeholder answer until RAG pipeline is wired.

Models:
  - AskFilters → optional scoping (jurisdiction, agency).
  - AskRequest → POST body with question, filters, top_k.
  - Citation (TypedDict) → URL, excerpt, score.
  - AskResponse → structured response with answer, citations, used_filters.

Dependencies:
  - Depends(get_settings) for access to configured Settings.

Common examples:
  curl -X POST "http://127.0.0.1:8000/ask" \
       -H "Content-Type: application/json" \
       -d '{"q":"What are the NFPA 30 storage rules?","filters":{"jurisdiction":"CO"},"top_k":5}'
"""

from __future__ import annotations
from typing import List, Optional, TypedDict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from settings import Settings, get_settings

router = APIRouter(prefix="/ask", tags=["ask"])


class AskFilters(BaseModel):
    """Optional filters to scope retrieval."""
    jurisdiction: Optional[str] = None
    agency: Optional[str] = None


class AskRequest(BaseModel):
    """Incoming request schema for Q&A."""
    q: str = Field(..., min_length=3)
    filters: Optional[AskFilters] = None
    top_k: int = Field(6, ge=1, le=20)


class Citation(TypedDict):
    """Lightweight citation for RAG answers."""
    url: str
    excerpt: str
    score: float


class AskResponse(BaseModel):
    """Structured response with synthesized answer + supporting citations."""
    answer: str
    citations: List[Citation]
    used_filters: Optional[AskFilters] = None


@router.post("", response_model=AskResponse)
def ask(req: AskRequest, cfg: Settings = Depends(get_settings)) -> AskResponse:
    """
    Handle Q&A requests.
    TODO: wire into retriever + LLM synthesis pipeline (Gemini/GPT).
    Currently returns a placeholder answer and mock citation.
    """
    return AskResponse(
        answer="This is a placeholder answer. RAG pipeline not wired yet.",
        citations=[
            {"url": "https://example.gov/reg/123", "excerpt": "…example excerpt…", "score": 0.82}
        ],
        used_filters=req.filters,
    )
