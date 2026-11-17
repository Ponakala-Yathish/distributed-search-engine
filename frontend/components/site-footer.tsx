import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-paper-raised">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-3 px-5 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
        <p>Index Atlas — a clear view into distributed retrieval.</p>
        <nav aria-label="Footer navigation" className="flex gap-5">
          <Link className="hover:text-ink" href="/">
            Search
          </Link>
          <Link className="hover:text-ink" href="/analytics">
            Analytics
          </Link>
        </nav>
      </div>
    </footer>
  );
}
