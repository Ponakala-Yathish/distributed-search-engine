export interface SearchResult {
  document_id: string;
  title: string;
  url: string;
  bm25_score: number;
  pagerank_score: number;
  final_score: number;
  explanation: string;
  ranking_details?: {
    bm25: { normalized: number };
    pagerank: { normalized: number };
  };
}

export interface SearchResponse {
  query: string;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  latency_ms: number;
  index_version: string;
  results: SearchResult[];
}

export type StatsValue =
  | string
  | number
  | boolean
  | null
  | StatsValue[]
  | { [key: string]: StatsValue };

export interface StatsResponse {
  total_documents?: number;
  index_size_bytes?: number;
  shard_count?: number;
  queries_processed?: number;
  avg_latency_ms?: number;
  uptime_seconds?: number;
  [key: string]: StatsValue | undefined;
}

export interface HealthResponse {
  status?: string;
  version?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface VersionResponse {
  version?: string;
  index_version?: string;
  commit?: string;
  built_at?: string;
  [key: string]: unknown;
}

export interface DocumentResponse {
  document_id?: string;
  title?: string;
  url?: string;
  content?: string;
  text?: string;
  metadata?: Record<string, unknown>;
  bm25_score?: number;
  pagerank_score?: number;
  final_score?: number;
  explanation?: string;
  [key: string]: unknown;
}
