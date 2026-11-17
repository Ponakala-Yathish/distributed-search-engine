import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-4xl px-5 py-16 text-center sm:px-8 lg:px-12">
      <p className="text-sm font-bold uppercase tracking-[0.12em] text-cobalt">404</p>
      <h1 className="mt-4 text-4xl font-bold tracking-[-0.04em]">This page is not in the index</h1>
      <p className="mx-auto mt-4 max-w-reading leading-7 text-muted">
        The requested route does not exist. Search the corpus or return to the analytics overview.
      </p>
      <div className="mt-8 flex justify-center gap-5">
        <Link href="/" className="border-b-2 border-cobalt pb-1 text-sm font-bold text-cobalt">
          Search
        </Link>
        <Link href="/analytics" className="border-b-2 border-ink pb-1 text-sm font-bold text-ink">
          Analytics
        </Link>
      </div>
    </div>
  );
}
