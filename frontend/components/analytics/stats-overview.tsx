import { formatBytes, formatDuration, formatNumber, formatStatLabel } from "@/lib/format";
import type { StatsResponse, StatsValue } from "@/lib/types";

interface StatsOverviewProps {
  stats: StatsResponse;
}

interface MetricDefinition {
  label: string;
  keys: string[];
  format: (value: number) => string;
}

const metricDefinitions: MetricDefinition[] = [
  {
    label: "Indexed documents",
    keys: ["total_documents", "document_count", "documents"],
    format: formatNumber,
  },
  {
    label: "Index size",
    keys: ["index_size_bytes", "index_size", "size_bytes"],
    format: formatBytes,
  },
  {
    label: "Active shards",
    keys: ["shard_count", "shards", "active_shards"],
    format: formatNumber,
  },
  {
    label: "Queries processed",
    keys: ["queries_processed", "query_count", "total_queries"],
    format: formatNumber,
  },
  {
    label: "Average latency",
    keys: ["avg_latency_ms", "average_latency_ms", "latency_ms"],
    format: (value) => `${formatNumber(value)} ms`,
  },
  {
    label: "Service uptime",
    keys: ["uptime_seconds", "uptime"],
    format: formatDuration,
  },
];

function readNumber(stats: StatsResponse, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = stats[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }

  return undefined;
}

function formatStatValue(value: StatsValue): string {
  if (value === null) {
    return "Not available";
  }

  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => formatStatValue(item)).join(", ") : "None";
  }

  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => `${formatStatLabel(key)}: ${formatStatValue(item)}`)
      .join(" · ");
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "number") {
    return new Intl.NumberFormat("en-US").format(value);
  }

  return value;
}

export function StatsOverview({ stats }: StatsOverviewProps) {
  const knownKeys = new Set(metricDefinitions.flatMap((metric) => metric.keys));
  const additionalEntries = Object.entries(stats).filter(
    ([key, value]) => !knownKeys.has(key) && value !== undefined,
  );

  return (
    <section aria-labelledby="index-ledger-heading">
      <div className="flex flex-col gap-3 border-b border-ink pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="index-ledger-heading" className="text-3xl font-bold tracking-[-0.03em]">
            Index ledger
          </h2>
          <p className="mt-2 max-w-reading text-sm leading-6 text-muted">
            Current measurements reported directly by the search service.
          </p>
        </div>
        <p className="text-sm font-semibold text-muted">Live /stats snapshot</p>
      </div>

      <dl className="grid border-x border-b border-line sm:grid-cols-2 lg:grid-cols-3">
        {metricDefinitions.map((metric) => {
          const value = readNumber(stats, metric.keys);

          return (
            <div key={metric.label} className="border-t border-line p-5 sm:p-6 lg:border-r lg:last:border-r-0">
              <dt className="text-sm font-semibold text-muted">{metric.label}</dt>
              <dd className="mt-2 text-3xl font-bold tracking-[-0.03em] tabular-nums text-ink">
                {value === undefined ? "—" : metric.format(value)}
              </dd>
              <p className="mt-2 text-xs text-muted">
                {value === undefined ? "Not reported by the service" : "Current value"}
              </p>
            </div>
          );
        })}
      </dl>

      {additionalEntries.length > 0 ? (
        <div className="mt-10">
          <h3 className="text-xl font-bold tracking-[-0.02em]">Additional service fields</h3>
          <div className="mt-4 overflow-x-auto border-t border-line">
            <table className="w-full min-w-[540px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="py-3 pr-5 font-bold text-ink">Field</th>
                  <th scope="col" className="py-3 font-bold text-ink">Value</th>
                </tr>
              </thead>
              <tbody>
                {additionalEntries.map(([key, value]) => (
                  <tr key={key} className="border-b border-line align-top">
                    <th scope="row" className="py-3 pr-5 font-semibold text-ink">
                      {formatStatLabel(key)}
                    </th>
                    <td className="max-w-[38rem] py-3 leading-6 text-muted">
                      {formatStatValue(value as StatsValue)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
