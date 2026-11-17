import Link from "next/link";

import { GraphIcon } from "@/components/icons";
import { SearchForm } from "@/components/search/search-form";
import { getHealth, getVersion } from "@/lib/api";

export const dynamic = "force-dynamic";

function statusLabel(status: string | undefined): string {
  if (!status) {
    return "responding";
  }

  return status.replace(/[_-]+/g, " ");
}

export default async function HomePage() {
  const [healthResult, versionResult] = await Promise.allSettled([getHealth(), getVersion()]);
  const health = healthResult.status === "fulfilled" ? healthResult.value : null;
  const version = versionResult.status === "fulfilled" ? versionResult.value : null;
  const status = typeof health?.status === "string" ? health.status : undefined;
  const indexVersion =
    typeof version?.index_version === "string"
      ? version.index_version
      : typeof version?.version === "string"
        ? version.version
        : "Unavailable";

  return (
    <>
      <section className="border-b border-line">
        <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-12 lg:px-12 lg:py-28">
          <div className="lg:col-span-8">
            <h1 className="max-w-4xl text-5xl font-bold leading-[0.98] tracking-[-0.045em] text-ink sm:text-6xl lg:text-7xl">
              Search the index. See why it matters.
            </h1>
            <p className="mt-6 max-w-reading text-lg leading-8 text-muted">
              Query a distributed corpus and inspect the ranking signals behind every result, from lexical relevance to authority.
            </p>

            <div className="mt-9 max-w-3xl">
              <SearchForm />
            </div>
          </div>

          <aside className="border-t border-ink pt-5 lg:col-span-4 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0" aria-label="Index status">
            <div className="flex items-start justify-between gap-6">
              <div>
                <h2 className="text-lg font-bold tracking-[-0.015em]">Live index</h2>
                <p className="mt-1 text-sm text-muted">Current service and index state</p>
              </div>
              <GraphIcon className="h-9 w-9 text-cobalt" />
            </div>

            <dl className="mt-8 divide-y divide-line border-y border-line">
              <div className="flex items-center justify-between gap-4 py-4">
                <dt className="text-sm font-semibold text-muted">Service</dt>
                <dd className="flex items-center gap-2 text-sm font-bold text-ink">
                  <span
                    className={`h-2 w-2 rounded-full ${status ? "bg-healthy" : "bg-line"}`}
                    aria-hidden="true"
                  />
                  {statusLabel(status)}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4 py-4">
                <dt className="text-sm font-semibold text-muted">Index version</dt>
                <dd className="max-w-[12rem] truncate text-sm font-bold tabular-nums text-ink" title={indexVersion}>
                  {indexVersion}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4 py-4">
                <dt className="text-sm font-semibold text-muted">Ranking</dt>
                <dd className="text-sm font-bold text-ink">BM25 + PageRank</dd>
              </div>
            </dl>

            <Link
              href="/analytics"
              className="mt-7 inline-flex items-center gap-2 border-b-2 border-cobalt pb-1 text-sm font-bold text-cobalt hover:border-cobalt-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
            >
              Open index analytics
              <span aria-hidden="true">→</span>
            </Link>
          </aside>
        </div>
      </section>

      <section className="mx-auto grid max-w-[1440px] gap-8 px-5 py-12 sm:px-8 lg:grid-cols-12 lg:px-12">
        <div className="lg:col-span-4">
          <h2 className="text-2xl font-bold tracking-[-0.025em]">A search built for inspection</h2>
        </div>
        <div className="grid gap-8 sm:grid-cols-2 lg:col-span-8">
          <div className="border-t border-line pt-4">
            <h3 className="font-bold">Transparent ordering</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Read the final score alongside BM25, PageRank, and the engine’s relevance explanation.
            </p>
          </div>
          <div className="border-t border-line pt-4">
            <h3 className="font-bold">Operational context</h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Check latency, index version, and service health without leaving the search workflow.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
