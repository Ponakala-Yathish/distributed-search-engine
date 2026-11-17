# Index Atlas frontend

A responsive Next.js interface for the distributed search engine. It provides editorial search, explainable ranking scores, paginated results, document inspection, and a live analytics view.

## Stack

- Next.js App Router
- React and TypeScript in strict mode
- Tailwind CSS
- Server-side API requests through a typed client

## Requirements

- Node.js 20.9 or newer
- npm
- A reachable search API

## Setup

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Configuration

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
SEARCH_API_TOKEN=
```

`NEXT_PUBLIC_API_BASE_URL` is the only browser-visible backend URL. It defaults to `http://localhost:8000` when unset. `SEARCH_API_TOKEN` is optional, server-only, and sent as a bearer token when present; it is never included in the client bundle.

Do not use a virtual-machine IP in source control. Configure the API host in the deployment environment instead.

## Commands

```bash
npm run dev
npm run build
npm run start
npm run lint
npm run typecheck
```

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Search entry point and live index status |
| `/search?q=...&page=1` | Ranked results, score explanation, and pagination |
| `/documents/[docId]` | Document details and ranking context |
| `/analytics` | Live statistics from `/stats`, plus health and version details |

## API contract

The frontend reads these endpoints from `NEXT_PUBLIC_API_BASE_URL`:

- `GET /health`
- `GET /search?q=...&page=1&page_size=10`
- `GET /stats`
- `GET /version`
- `GET /documents/{doc_id}`

The typed request and response definitions live in `lib/types.ts`. The server-only client in `lib/api.ts` normalizes timeouts, HTTP errors, and unavailable-service responses into consistent UI states.

## Structure

```text
app/                  App Router pages and route states
components/search/    Search form, result card, and pagination
components/analytics/ Analytics ledger
components/ui/        Shared states and loading skeletons
lib/api.ts            Server-only typed API client
lib/types.ts          API contract types
```
