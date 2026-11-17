from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody


class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=256)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    url: str
    bm25_score: float
    pagerank_score: float
    final_score: float
    explanation: str
    ranking_details: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    total: int
    total_pages: int
    latency_ms: float
    index_version: str
    results: list[SearchResult]


class HealthResponse(BaseModel):
    status: str
    version: str
    document_count: int
    serving_root: str


class StatsResponse(BaseModel):
    version: str
    phase: str
    created_at: str
    document_count: int
    total_documents: int
    avg_document_length: float
    term_count: int
    posting_count: int
    bm25: dict[str, float]
    pagerank: dict[str, float | int]


class VersionResponse(BaseModel):
    version: str
    phase: str
    created_at: str
    serving_root: str
    current_path: str
    available_versions: list[str]


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    url: str
    text: str
    doc_length: int
    pagerank_score: float
    index_version: str
