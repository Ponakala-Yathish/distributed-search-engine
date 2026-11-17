import type { Metadata } from "next";

import { Pagination } from "@/components/search/pagination";
import { ResultCard } from "@/components/search/result-card";
import { SearchForm } from "@/components/search/search-form";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorNotice } from "@/components/ui/error-notice";
import { getSearch } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { SearchResponse } from "@/lib/types";

export const metadata: Metadata = {
  title: "Search",
};

export const dynamic = "force-dynamic";

interface SearchPageProps {
  searchParams: Promise<{ q?: string | string[]; page?: string | string[] }>;
}

function firstValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

async function loadSearch(query: string, page: number): Promise<SearchResponse | null> {
  try {
    return await getSearch(query, page);
  } catch {
    return null;
  }
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  const query = firstValue(params.q).trim();
  const requestedPage = Number.parseInt(firstValue(params.page), 10);
  const page = Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1;

  if (!query) {
    return (
      <div className="mx-auto max-w-4xl px-5 py-12 sm:px-8 lg:px-12">
        <h1 className="text-4xl font-bold tracking-[-0.035em] sm:text-5xl">Search the index</h1>
        <div className="mt-8">
          <SearchForm />
        </div>
        <div className="mt-12">
          <EmptyState
            title="Start with a query"
            message="Enter a topic, phrase, or document identifier to search the distributed index."
          />
        </div>
      </div>
    );
  }

  const response = await loadSearch(query, page);
  if (!response) {
    return (
      <div className="mx-auto max-w-4xl px-5 py-12 sm:px-8 lg:px-12">
        <h1 className="text-3xl font-bold tracking-[-0.035em]">Search unavailable</h1>
        <div className="mt-8">
          <SearchForm defaultValue={query} compact />
        </div>
        <div className="mt-8">
          <ErrorNotice />
        </div>
      </div>
    );
  }

  const maxBm25 = Math.max(...response.results.map((result) => result.bm25_score), 0);
  const maxPageRank = Math.max(...response.results.map((result) => result.pagerank_score), 0);

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-9 sm:px-8 lg:px-12 lg:py-12">
      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <h1 className="text-3xl font-bold tracking-[-0.035em] sm:text-4xl">
            Results for <span className="text-cobalt">“{response.query}”</span>
          </h1>
          <div className="mt-8">
            <SearchForm defaultValue={response.query} compact label="Refine your search" />
          </div>
        </div>

        <dl className="grid grid-cols-2 border-y border-line lg:col-span-4 lg:grid-cols-2">
          <div className="border-b border-line py-4 pr-4 lg:border-r">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Matches</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums">{formatNumber(response.total)}</dd>
          </div>
          <div className="border-b border-line py-4 pl-4 lg:border-r-0 lg:pl-4">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Latency</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums">{response.latency_ms} ms</dd>
          </div>
          <div className="py-4 pr-4">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Page</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums">
              {response.page} <span className="text-sm font-semibold text-muted">of {response.total_pages}</span>
            </dd>
          </div>
          <div className="py-4 pl-4">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Index</dt>
            <dd className="mt-1 truncate text-lg font-bold tabular-nums" title={response.index_version}>
              {response.index_version}
            </dd>
          </div>
        </dl>
      </div>

      {response.results.length > 0 ? (
        <>
          <div className="mt-10">
            {response.results.map((result, index) => (
              <ResultCard
                key={result.document_id}
                result={result}
                rank={(response.page - 1) * response.page_size + index + 1}
                scores={{
                  final: {
                    label: "Final",
                    value: result.final_score,
                    percentage: result.final_score * 100,
                  },
                  bm25: {
                    label: "BM25",
                    value: result.bm25_score,
                    percentage: result.ranking_details
                      ? result.ranking_details.bm25.normalized * 100
                      : maxBm25 > 0
                        ? (result.bm25_score / maxBm25) * 100
                        : 0,
                  },
                  pagerank: {
                    label: "PageRank",
                    value: result.pagerank_score,
                    percentage: result.ranking_details
                      ? result.ranking_details.pagerank.normalized * 100
                      : maxPageRank > 0
                        ? (result.pagerank_score / maxPageRank) * 100
                        : 0,
                  },
                }}
              />
            ))}
          </div>
          <Pagination query={response.query} currentPage={response.page} totalPages={response.total_pages} />
        </>
      ) : (
        <div className="mt-12">
          <EmptyState
            title="No matching documents"
            message="Try a broader phrase, check the spelling, or search for a concept related to the original query."
          />
        </div>
      )}
    </div>
  );
}
