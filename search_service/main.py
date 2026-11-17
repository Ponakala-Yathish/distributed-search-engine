from __future__ import annotations

import argparse
import asyncio
import logging
import os
import secrets
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import load_config, load_settings

from .bm25 import bm25_score
from .hybrid_ranker import rank_candidates
from .schemas import (
    DocumentResponse,
    HealthResponse,
    SearchResponse,
    SearchResult,
    StatsResponse,
    VersionResponse,
)
from .tokenizer import preprocess_query
from .version_manager import VersionManager

LOGGER = logging.getLogger("search_service")


def _manager_from_request(request: Request) -> VersionManager:
    return cast(VersionManager, request.app.state.version_manager)


def _error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


bearer_scheme = HTTPBearer(auto_error=False)


def _authorize(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    expected = os.getenv("SEARCH_API_TOKEN")
    if not expected:
        return
    supplied = credentials.credentials if credentials is not None else ""
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid or missing bearer token")


def _resolve_serving_root(config: dict[str, Any], override: str | Path | None = None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    value = config.get("paths", {}).get("local", {}).get("serving_root")
    if not value:
        raise ValueError("serving root is missing from the configuration")
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path.resolve()


def create_app(
    version_manager: VersionManager | None = None,
    serving_root: str | Path | None = None,
    config: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    reload_interval: float | None = None,
) -> FastAPI:
    loaded_config = config if config is not None else load_config()
    loaded_settings = settings if settings is not None else load_settings()
    search_settings = loaded_settings.get("search", {})
    max_query_length = int(search_settings.get("max_query_length", 256))
    default_page_size = int(search_settings.get("default_page_size", 10))
    max_page_size = int(search_settings.get("max_page_size", 50))
    configured_reload_interval = float(search_settings.get("index_reload_interval_seconds", 30))
    effective_reload_interval = configured_reload_interval if reload_interval is None else float(reload_interval)
    if effective_reload_interval <= 0:
        raise ValueError("reload interval must be positive")
    manager = version_manager or VersionManager(_resolve_serving_root(loaded_config, serving_root))

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        stop_event = asyncio.Event()
        await asyncio.to_thread(manager.initialize)
        if effective_reload_interval > 0:
            async def reload_loop() -> None:
                while not stop_event.is_set():
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=effective_reload_interval)
                    except asyncio.TimeoutError:
                        try:
                            await asyncio.to_thread(manager.reload_current)
                        except Exception:
                            LOGGER.exception("index reload failed; retaining the active version")

            reload_task = asyncio.create_task(reload_loop())
        else:
            reload_task = None
        try:
            yield
        finally:
            stop_event.set()
            if reload_task is not None:
                await reload_task
            manager.close()

    application = FastAPI(
        title="Distributed Search Engine",
        version="1.0.0",
        lifespan=lifespan,
        dependencies=[Depends(_authorize)],
    )
    application.state.version_manager = manager

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        if exc.status_code == 503:
            code = "service_unavailable"
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code, detail),
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error",
                "request validation failed",
                jsonable_encoder(exc.errors()),
            ),
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        LOGGER.exception("unhandled request error")
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "internal server error"),
        )

    @application.get("/health", response_model=HealthResponse)
    async def health(manager: VersionManager = Depends(_manager_from_request)) -> HealthResponse:
        snapshot = manager.active
        if snapshot is None:
            raise HTTPException(status_code=503, detail="no active index version")
        return HealthResponse(
            status="ok",
            version=snapshot.version,
            document_count=snapshot.document_count,
            serving_root=str(manager.serving_root),
        )

    @application.get("/search", response_model=SearchResponse)
    async def search(
        request: Request,
        q: str = Query(min_length=1, max_length=max_query_length),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=default_page_size, ge=1, le=max_page_size),
        manager: VersionManager = Depends(_manager_from_request),
    ) -> SearchResponse:
        started = time.perf_counter()
        query = q.strip()
        terms = preprocess_query(query)
        if not terms:
            raise HTTPException(status_code=422, detail="query must contain at least one searchable term")
        snapshot = manager.active
        if snapshot is None:
            raise HTTPException(status_code=503, detail="no active index version")
        scores = bm25_score(
            terms,
            snapshot.postings,
            snapshot.doc_lengths,
            snapshot.total_documents,
            snapshot.avg_document_length,
            {term: stats.idf for term, stats in snapshot.terms.items()},
            snapshot.bm25["k1"],
            snapshot.bm25["b"],
        )
        ranked = rank_candidates(scores, snapshot.pagerank_scores)
        total_results = len(ranked)
        total_pages = (total_results + page_size - 1) // page_size
        offset = (page - 1) * page_size
        selected = ranked[offset : offset + page_size]
        results: list[SearchResult] = []
        for item in selected:
            document = snapshot.documents[item.doc_id]
            matched_terms = sorted(term for term in terms if item.doc_id in snapshot.postings.get(term, {}))
            details = {
                "formula": "0.7 * (bm25 / max_bm25) + 0.3 * (pagerank / max_pagerank)",
                "matched_terms": matched_terms,
                "bm25": {
                    "raw": item.bm25_score,
                    "normalized": item.bm25_normalized,
                    "weighted": 0.7 * item.bm25_normalized,
                },
                "pagerank": {
                    "raw": item.pagerank,
                    "normalized": item.pagerank_normalized,
                    "weighted": 0.3 * item.pagerank_normalized,
                },
            }
            explanation = (
                f"Matched {', '.join(matched_terms)}. "
                f"Normalized BM25 {item.bm25_normalized:.4f} contributes "
                f"{0.7 * item.bm25_normalized:.4f}; normalized PageRank "
                f"{item.pagerank_normalized:.4f} contributes "
                f"{0.3 * item.pagerank_normalized:.4f}."
            )
            results.append(
                SearchResult(
                    document_id=item.doc_id,
                    title=document.title,
                    url=document.url,
                    bm25_score=item.bm25_score,
                    pagerank_score=item.pagerank,
                    final_score=item.score,
                    explanation=explanation,
                    ranking_details=details,
                )
            )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response = SearchResponse(
            query=query,
            page=page,
            page_size=page_size,
            total=total_results,
            total_pages=total_pages,
            latency_ms=elapsed_ms,
            index_version=snapshot.version,
            results=results,
        )
        request.state.latency_ms = elapsed_ms
        return response

    @application.get("/stats", response_model=StatsResponse)
    async def stats(manager: VersionManager = Depends(_manager_from_request)) -> StatsResponse:
        snapshot = manager.active
        if snapshot is None:
            raise HTTPException(status_code=503, detail="no active index version")
        return StatsResponse(
            version=snapshot.version,
            phase=snapshot.phase,
            created_at=snapshot.created_at,
            document_count=snapshot.document_count,
            total_documents=snapshot.total_documents,
            avg_document_length=snapshot.avg_document_length,
            term_count=snapshot.term_count,
            posting_count=snapshot.posting_count,
            bm25=snapshot.bm25,
            pagerank=snapshot.pagerank,
        )

    @application.get("/version", response_model=VersionResponse)
    async def version(manager: VersionManager = Depends(_manager_from_request)) -> VersionResponse:
        snapshot = manager.active
        if snapshot is None:
            raise HTTPException(status_code=503, detail="no active index version")
        return VersionResponse(
            version=snapshot.version,
            phase=snapshot.phase,
            created_at=snapshot.created_at,
            serving_root=str(manager.serving_root),
            current_path=str(manager.current_path),
            available_versions=manager.available_versions(),
        )

    @application.get("/documents/{doc_id}", response_model=DocumentResponse)
    async def document(
        doc_id: str,
        manager: VersionManager = Depends(_manager_from_request),
    ) -> DocumentResponse:
        snapshot = manager.active
        if snapshot is None:
            raise HTTPException(status_code=503, detail="no active index version")
        record = snapshot.documents.get(doc_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"document not found: {doc_id}")
        return DocumentResponse(
            document_id=record.doc_id,
            title=record.title,
            url=record.url,
            text=record.text,
            doc_length=record.doc_length,
            pagerank_score=snapshot.pagerank_scores[record.doc_id],
            index_version=snapshot.version,
        )

    return application


app = create_app()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and serve a distributed search index")
    parser.add_argument("--config", default=None, help="cluster configuration file")
    parser.add_argument("--settings", default=None, help="service settings file")
    parser.add_argument("--serving-root", default=None, help="local directory containing exported versions")
    parser.add_argument("--host", default=None, help="HTTP bind host")
    parser.add_argument("--port", default=None, type=int, help="HTTP bind port")
    parser.add_argument(
        "--reload-interval",
        default=None,
        type=float,
        help="background index reload interval in seconds",
    )
    parser.add_argument("--validate", action="store_true", help="validate exported index versions and exit")
    parser.add_argument("--serve", action="store_true", help="run the HTTP service")
    return parser


def _environment_host(settings: dict[str, Any]) -> str:
    return os.getenv("DSE_SEARCH_HOST") or os.getenv("SEARCH_HOST") or str(settings.get("search", {}).get("host", ""))


def _environment_port(settings: dict[str, Any]) -> int:
    value = os.getenv("DSE_SEARCH_PORT") or os.getenv("SEARCH_PORT")
    if value is not None:
        return int(value)
    return int(settings.get("search", {}).get("port", 0))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        settings = load_settings(args.settings)
        serving_root = _resolve_serving_root(config, args.serving_root)
        host = args.host or _environment_host(settings)
        port = args.port if args.port is not None else _environment_port(settings)
        if not host:
            raise ValueError("search host is missing from the configuration")
        if not 1 <= port <= 65535:
            raise ValueError("search port must be between 1 and 65535")
        manager = VersionManager(serving_root)
        if args.validate:
            results = manager.validate_versions()
            if not results:
                print("No index versions found", file=sys.stderr)
                return 1
            failed = False
            for name, error in results.items():
                if error is None:
                    print(f"{name}: valid")
                else:
                    failed = True
                    print(f"{name}: invalid: {error}", file=sys.stderr)
            manager.initialize()
            return 1 if failed else 0
        application = create_app(
            version_manager=manager,
            config=config,
            settings=settings,
            reload_interval=args.reload_interval,
        )
        uvicorn.run(application, host=host, port=port)
        return 0
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
