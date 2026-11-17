---
version: 1
slug: "app-page-tsx"
primary_target: "app/page.tsx"
related_targets: ["app/search/page.tsx","app/analytics/page.tsx"]
---

# Search and analytics surface brief

## Scope and visitor mode

Mode: Operate. Covers the homepage, search results, document detail, and analytics dashboard for a distributed search engine.

## Audience, job, and constraints

Engineers, researchers, and operators search the corpus, inspect ranking evidence, and monitor index health. Standard web controls remain familiar; the design must stay fast, responsive, accessible, and free of invented performance claims or data.

## Direction and memorable moment

A printed research-index folio on warm paper: strong typography, hairline registration rules, and a restrained cobalt relevance trace that visibly links the three ranking signals. The trace is functional and becomes the visual link between result cards and dashboard charts.

## Unresolved decisions

Analytics card names remain tolerant of several plausible `/stats` response shapes because only the endpoint is specified. The interface should surface known fields without rejecting valid variants.

## Direction contract

THESIS: Search should feel like consulting a precise research index, not scanning a grid of generic cards; it refuses the category default of an oversized hero followed by a list of interchangeable result tiles.

OWN-WORLD: Warm near-white paper, near-black ink, one restrained cobalt accent, hairline rules, a disciplined 12-column grid, a high-legibility grotesk for display and text, tabular figures for measurements, and square or barely-rounded controls. Graph lines appear only to explain relationships between ranking signals, health, and latency.

STORY: The visitor arrives with a query, understands result order and its evidence at a glance, moves through pages without losing context, and can pivot from a result to system analytics while retaining confidence that the numbers are live.

FIRST VIEWPORT: A compact responsive header holds the product name, search, and route navigation. The homepage opens directly into a large but disciplined search field with recent query guidance and a small live-service status line. Results replace the homepage introduction with a compact query ledger, followed by ranked result cards on a broad reading column with a narrow evidence rail.

FORM: Chosen challenger 2 from the design-annual plate section, adapted to the brief’s ink-and-paper requirement. The seed reference is seed:da3dc017b75731e4.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
