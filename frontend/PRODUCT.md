# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: Next.js App Router, TypeScript strict mode, Tailwind CSS, and a browser-safe API base URL supplied by `NEXT_PUBLIC_API_BASE_URL`.

## Users

Inferred from the requested analytics and ranking-explanation features: engineers, researchers, and operators who need to query the index, understand result relevance, and monitor search-system health.

## Product Purpose

Provide fast, understandable access to a distributed search engine. Success means users can find relevant documents, inspect why each result was ranked, and review operational index statistics without navigating infrastructure-specific tools.

## Positioning

A search interface that exposes the distributed engine’s hybrid ranking signals—BM25, PageRank, and final score—rather than presenting relevance as an opaque total.

## Operating Context

Users search from a browser, move between result pages, inspect individual documents, and consult analytics for current index health and usage information.

## Capabilities and Constraints

- Search results expose title, URL, document ID, BM25 score, PageRank score, final score, and ranking explanation.
- Results are paginated and report query, page, page size, totals, latency, and index version.
- Analytics are available from `/stats`; document detail is available from `/documents/{doc_id}`.
- Browser requests use only `NEXT_PUBLIC_API_BASE_URL`, defaulting to localhost.
- The frontend contains no hardcoded virtual-machine IP address.

## Brand Commitments

Editorial search with minimalist, professional, fast character; ink-and-paper tones; strong typography; subtle graph-inspired accents; responsive and uncrowded presentation.

## Evidence on Hand

The backend API contract is confirmed by the product brief. No real index data, screenshots, brand assets, or performance claims are available, so the interface must not fabricate them.

## Product Principles

1. Make relevance inspectable, not mysterious.
2. Keep the fastest useful path obvious.
3. Use structure and typography before ornament.
4. Treat operational state as part of the reading experience.
5. Make accessibility and resilience default behaviors.

## Accessibility & Inclusion

Accessibility matters: semantic structure, visible keyboard focus, sufficient contrast, screen-reader labels, reduced-motion support, responsive layouts, and explicit loading, empty, and error states are required.
