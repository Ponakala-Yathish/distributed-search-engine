import Link from "next/link";

import { ArrowUpRightIcon } from "@/components/icons";
import { formatScore } from "@/lib/format";
import type { SearchResult } from "@/lib/types";

interface ScoreDatum {
  label: string;
  value: number;
  percentage: number;
}

interface ResultCardProps {
  result: SearchResult;
  rank: number;
  scores: {
    final: ScoreDatum;
    bm25: ScoreDatum;
    pagerank: ScoreDatum;
  };
}

function displayUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.hostname}${parsed.pathname === "/" ? "" : parsed.pathname}`;
  } catch {
    return url;
  }
}

function ScoreTrack({ datum }: { datum: ScoreDatum }) {
  const percentage = Math.max(2, Math.min(100, datum.percentage));

  return (
    <div className="grid grid-cols-[74px_1fr_54px] items-center gap-2 text-xs">
      <span className="font-semibold text-muted">{datum.label}</span>
      <span
        className="relative h-px bg-line"
        role="img"
        aria-label={`${datum.label}: ${formatScore(datum.value)}`}
      >
        <span
          className="absolute inset-y-0 left-0 bg-cobalt transition-[width] duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
        <span
          className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cobalt bg-paper-raised"
          style={{ left: `${percentage}%` }}
          aria-hidden="true"
        />
      </span>
      <span className="text-right font-semibold tabular-nums text-ink">{formatScore(datum.value)}</span>
    </div>
  );
}

export function ResultCard({ result, rank, scores }: ResultCardProps) {
  const headingId = `result-${result.document_id}`;

  return (
    <article className="grid gap-5 border-b border-line py-8 md:grid-cols-[48px_minmax(0,1fr)_190px] md:gap-7">
      <div className="flex items-baseline gap-2 md:block" aria-label={`Rank ${rank}`}>
        <span className="text-xs font-bold uppercase tracking-[0.12em] text-muted md:hidden">Rank</span>
        <span className="font-serif text-2xl font-bold tabular-nums text-cobalt">{rank}</span>
      </div>

      <div className="min-w-0">
        <h2 id={headingId} className="text-xl font-bold leading-tight tracking-[-0.015em] text-ink sm:text-2xl">
          <a
            href={result.url}
            target="_blank"
            rel="noreferrer"
            className="inline decoration-cobalt/50 decoration-2 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
          >
            {result.title || result.document_id}
            <ArrowUpRightIcon className="ml-2 inline h-4 w-4 -translate-y-0.5 text-muted" />
          </a>
        </h2>
        <p className="mt-2 truncate text-sm text-muted" title={result.url}>
          {displayUrl(result.url)}
        </p>
        <p className="mt-5 max-w-reading text-[15px] leading-7 text-ink/85">
          {result.explanation || "The engine returned this document for the submitted query."}
        </p>
        <Link
          href={`/documents/${encodeURIComponent(result.document_id)}`}
          className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-cobalt hover:text-cobalt-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
        >
          Inspect document
          <span aria-hidden="true">→</span>
        </Link>
      </div>

      <aside className="border-t border-line pt-4 md:border-l md:border-t-0 md:pl-6 md:pt-0" aria-label={`Ranking scores for ${result.title}`}>
        <div className="flex items-end justify-between md:block">
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Final score</p>
          <p className="text-3xl font-bold tracking-[-0.03em] tabular-nums text-ink md:mt-1">
            {formatScore(result.final_score)}
          </p>
        </div>
        <div className="mt-5 space-y-3">
          <ScoreTrack datum={scores.bm25} />
          <ScoreTrack datum={scores.pagerank} />
          <ScoreTrack datum={scores.final} />
        </div>
      </aside>
    </article>
  );
}
