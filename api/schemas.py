"""Pydantic request/response models for the web API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None


class CaseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None


class CaseSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    mode: Literal["imported", "live"] = "imported"
    created_at: Optional[datetime] = None
    evidence_count: int = 0
    event_count: int = 0


class FindingSummary(BaseModel):
    id: str
    kind: Literal["rule", "story"]
    headline: str
    detail: str = ""
    severity_label: str = "Informational"
    related_event_ids: list[str] = Field(default_factory=list)


class CaseDetail(CaseSummary):
    last_analysis_at: Optional[datetime] = None
    top_findings: list[FindingSummary] = Field(default_factory=list)
    relationship_count: int = 0
    finding_count: int = 0
    story_count: int = 0


class EvidenceSummary(BaseModel):
    id: str
    filename: str
    source_type: str
    sha256_hash: str
    file_size: int
    integrity_status: str
    status_label: str
    created_at: Optional[datetime] = None


class AnalyzeRequest(BaseModel):
    evidence_ids: Optional[list[str]] = None


class JobStatus(BaseModel):
    id: str
    case_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    result_summary: Optional[dict[str, Any]] = None


class EventSummary(BaseModel):
    id: str
    timestamp: Optional[datetime] = None
    source_type: str
    event_type: str
    classification: str = "UNKNOWN"
    headline: str
    detail: str = ""
    severity_label: str = "Informational"


class EventDetail(EventSummary):
    evidence_id: Optional[str] = None
    technical: dict[str, Any] = Field(default_factory=dict)


class EventPage(BaseModel):
    total: int
    items: list[EventSummary]


class FindingsResponse(BaseModel):
    findings: list[FindingSummary]
    stories: list[FindingSummary]


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str
    story: str = ""


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: str
    confidence: Optional[float] = None


class GraphResponse(BaseModel):
    view: Literal["simple", "detailed"]
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class IntegrityRow(BaseModel):
    evidence_id: str
    what: str
    sha256_hash: str
    status: str
    status_label: str
    collected_at: Optional[datetime] = None


class IntegrityResponse(BaseModel):
    items: list[IntegrityRow]
    legend: dict[str, str]
