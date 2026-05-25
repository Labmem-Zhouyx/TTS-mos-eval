"""Pydantic schemas exchanged with the frontend."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SessionStart(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=64)
    language: str = Field("zh", pattern="^(zh|en)$")
    notes: Optional[str] = None


class SessionStartResponse(BaseModel):
    session_id: str
    nickname: str
    language: str
    started_at: str


class RatingSystem(BaseModel):
    """A single (sample, system) rating row."""

    system: str
    scores: Dict[str, Any] = Field(default_factory=dict)


class SampleRating(BaseModel):
    sample_id: str
    ratings: List[RatingSystem] = Field(default_factory=list)
    # ABX panels submit a single preference object here instead of per-system
    abx_choice: Optional[str] = None  # 'A', 'B', or 'tie'
    notes: Optional[str] = None


class PanelSubmission(BaseModel):
    panel: str
    samples: List[SampleRating] = Field(default_factory=list)
    status: str = Field("draft", pattern="^(draft|submitted)$")


class SessionUpdate(BaseModel):
    session_id: str
    nickname: Optional[str] = None
    language: Optional[str] = None
    panels: List[PanelSubmission] = Field(default_factory=list)
    final: bool = False
