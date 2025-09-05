from __future__ import annotations

from typing import List, Optional, TypedDict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from settings import Settings, get_settings

router = APIRouter(prefix="/ask", tags=["ask"])

class AskFilters(BaseModel):
    jurisdiction: Optional[str] = None
    agency: Optional[str] = None

class AskRequest(BaseModel):
    q: str = Field(..., min_length=3)
    filters: Optional[AskFilters] = None
    top_k: int = Field(6, ge=1, le=20)

class Citation(TypedDict):
    url: str
    excerpt: str
    score: float

class AskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    used_filters: Optional[AskFilters] = None

@router.post("", response_model=AskResponse)
def ask(req: AskRequest, cfg: Settings = Depends(get_settings)) -> AskResponse:
    # TODO: wire to retriever + Gemini/GPT synthesis
    # Placeholder response to keep frontends unblocked
    return AskResponse(
        answer="This is a placeholder answer. RAG pipeline not wired yet.",
        citations=[
            {"url": "https://example.gov/reg/123", "excerpt": "…example excerpt…", "score": 0.82}
        ],
        used_filters=req.filters,
    )
