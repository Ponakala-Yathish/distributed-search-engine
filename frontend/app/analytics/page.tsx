import type { Metadata } from "next";

import { StatsOverview } from "@/components/analytics/stats-overview";
import { ErrorNotice } from "@/components/ui/error-notice";
import { getHealth, getStats, getVersion } from "@/lib/api";

export const metadata: Metadata = {
  title: "Analytics",
};

export const dynamic = "force-dynamic";

function displayStatus(status: string | undefined): string {
  return status ? status.replace(/[_-]+/g, " ") : "Responding";
}

export default async function AnalyticsPage() {
  const [statsResult, versionResult, healthResult] = await Promise.allSettled([
    getStats(),
    getVersion(),
    getHealth(),
  ]);

  const stats = statsResult.status === "fulfilled" ? statsResult.value : null;
  const version = versionResult.status === "fulfilled" ? versionResult.value : null;
  const health = healthResult.status === "fulfilled" ? healthResult.value : null;
  const indexVersion =
    typeof version?.index_version === "string"
      ? version.index_version
      : typeof version?.version === "string"
        ? version.version
        : "Unavailable";
  const serviceStatus = typeof health?.status === "string" ? health.status : undefined;

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-10 sm:px-8 sm:py-14 lg:px-12">
      <div className="grid gap-8 border-b border-ink pb-10 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <h1 className="text-4xl font-bold tracking-[-0.04em] sm:text-5xl">Index analytics</h1>
          <p className="mt-4 max-w-reading text-lg leading-8 text-muted">
            A live operational view of corpus size, query activity, service latency, and the deployed index version.
          </p>
        </div>

        <dl className="grid grid-cols-2 border-y border-line lg:col-span-4 lg:grid-cols-1">
          <div className="border-b border-line py-4 pr-4 lg:border-r lg:border-b-0 lg:pr-0 lg:pl-6">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Service</dt>
            <dd className="mt-1 flex items-center gap-2 font-bold capitalize text-ink">
              <span className={`h-2 w-2 rounded-full ${serviceStatus ? "bg-healthy" : "bg-line"}`} aria-hidden="true" />
              {displayStatus(serviceStatus)}
            </dd>
          </div>
          <div className="py-4 pl-4 lg:border-r lg:border-t lg:border-line lg:py-4 lg:pl-6">
            <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Index version</dt>
            <dd className="mt-1 truncate font-bold tabular-nums text-ink" title={indexVersion}>
              {indexVersion}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-10">
        {stats ? (
          <StatsOverview stats={stats} />
        ) : (
          <ErrorNotice
            title="Index statistics are unavailable"
            message="The analytics endpoint did not respond. Other service details remain available above."
          />
        )}
      </div>
    </div>
  );
}
