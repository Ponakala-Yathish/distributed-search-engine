import Link from "next/link";
import { Suspense } from "react";

import { getHealth } from "@/lib/api";

import { GraphIcon } from "@/components/icons";
import { SiteNav } from "@/components/site-nav";

async function ServiceStatus() {
  const health = await getHealth().catch(() => null);
  const rawStatus = typeof health?.status === "string" ? health.status.toLowerCase() : "";
  const healthy = rawStatus === "ok" || rawStatus === "healthy";
  const label = health ? (healthy ? "Service healthy" : rawStatus || "Service responding") : "Status unavailable";

  return (
    <div className="flex items-center gap-2 text-xs font-semibold text-muted" aria-live="polite">
      <span
        className={`h-2 w-2 rounded-full ${healthy ? "bg-healthy" : rawStatus ? "bg-degraded" : "bg-line"}`}
        aria-hidden="true"
      />
      {label}
    </div>
  );
}

export function SiteHeader() {
  return (
    <header className="border-b border-line bg-paper-raised/95">
      <div className="mx-auto flex min-h-16 max-w-[1440px] items-center justify-between gap-5 px-5 sm:px-8 lg:px-12">
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4 focus-visible:ring-offset-paper-raised"
          aria-label="Index Atlas home"
        >
          <span className="grid h-9 w-9 place-items-center bg-ink text-paper-raised transition-colors group-hover:bg-cobalt">
            <GraphIcon className="h-6 w-6" />
          </span>
          <span>
            <span className="block text-[15px] font-bold leading-none tracking-[-0.01em]">Index Atlas</span>
            <span className="mt-1 block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
              Distributed search
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-4 sm:gap-7">
          <Suspense
            fallback={
              <div className="h-3 w-24 animate-pulse bg-line/70" aria-label="Checking service status" />
            }
          >
            <ServiceStatus />
          </Suspense>
          <SiteNav />
        </div>
      </div>
    </header>
  );
}
