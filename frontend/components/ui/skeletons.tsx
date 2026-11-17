export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-line/70 ${className}`} aria-hidden="true" />;
}

export function ResultSkeleton() {
  return (
    <article className="grid gap-5 border-b border-line py-8 md:grid-cols-[48px_minmax(0,1fr)_180px]">
      <Skeleton className="h-5 w-8" />
      <div>
        <Skeleton className="h-7 w-3/4" />
        <Skeleton className="mt-3 h-4 w-1/2" />
        <Skeleton className="mt-6 h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-5/6" />
      </div>
      <div className="space-y-4">
        <Skeleton className="h-9 w-20" />
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-2 w-4/5" />
      </div>
    </article>
  );
}

export function SearchLoading() {
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-10 sm:px-8 lg:px-12" aria-label="Loading search results">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="mt-4 h-12 w-full max-w-2xl" />
      <Skeleton className="mt-8 h-4 w-full max-w-xl" />
      <div className="mt-10">
        <ResultSkeleton />
        <ResultSkeleton />
        <ResultSkeleton />
      </div>
    </div>
  );
}

export function AnalyticsLoading() {
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-10 sm:px-8 lg:px-12" aria-label="Loading analytics">
      <Skeleton className="h-4 w-36" />
      <Skeleton className="mt-4 h-12 w-full max-w-xl" />
      <Skeleton className="mt-8 h-4 w-full max-w-2xl" />
      <div className="mt-12 grid border border-line sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="border-b border-line p-6 sm:border-r">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-4 h-10 w-32" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DocumentLoading() {
  return (
    <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8 lg:px-12" aria-label="Loading document">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-5 h-12 w-4/5" />
      <Skeleton className="mt-8 h-40 w-full" />
    </div>
  );
}
