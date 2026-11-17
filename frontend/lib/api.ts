import "server-only";

import type {
  DocumentResponse,
  HealthResponse,
  SearchResponse,
  StatsResponse,
  VersionResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_TOKEN = process.env.SEARCH_API_TOKEN;
const REQUEST_TIMEOUT_MS = 8_000;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status = 500) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function request<T>(path: string, validator?: (value: unknown) => value is T): Promise<T> {
  const normalizedBase = API_BASE_URL.endsWith("/") ? API_BASE_URL : `${API_BASE_URL}/`;
  const url = new URL(path.replace(/^\//, ""), normalizedBase);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiError(`Search service returned ${response.status}.`, response.status);
    }

    const payload: unknown = await response.json();

    if (validator && !validator(payload)) {
      throw new ApiError("Search service returned an unexpected response.", 502);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError("The search service did not respond in time.", 504);
    }

    throw new ApiError("The search service is currently unreachable.", 503);
  } finally {
    clearTimeout(timeout);
  }
}

function isSearchResponse(value: unknown): value is SearchResponse {
  if (!isRecord(value) || !Array.isArray(value.results)) {
    return false;
  }

  return (
    typeof value.query === "string" &&
    typeof value.page === "number" &&
    typeof value.page_size === "number" &&
    typeof value.total === "number" &&
    typeof value.total_pages === "number" &&
    typeof value.latency_ms === "number" &&
    typeof value.index_version === "string"
  );
}

function isRecordResponse(value: unknown): value is Record<string, unknown> {
  return isRecord(value);
}

export async function getSearch(
  query: string,
  page = 1,
  pageSize = 10,
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    page: String(page),
    page_size: String(pageSize),
  });

  return request<SearchResponse>(`search?${params.toString()}`, isSearchResponse);
}

export async function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>("stats", isRecordResponse as (value: unknown) => value is StatsResponse);
}

export async function getVersion(): Promise<VersionResponse> {
  return request<VersionResponse>("version", isRecordResponse as (value: unknown) => value is VersionResponse);
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("health", isRecordResponse as (value: unknown) => value is HealthResponse);
}

export async function getDocument(documentId: string): Promise<DocumentResponse> {
  return request<DocumentResponse>(
    `documents/${encodeURIComponent(documentId)}`,
    isRecordResponse as (value: unknown) => value is DocumentResponse,
  );
}
