import Link from "next/link";

import { ArrowLeftIcon, ArrowRightIcon } from "@/components/icons";

interface PaginationProps {
  query: string;
  currentPage: number;
  totalPages: number;
}

function pageHref(query: string, page: number): string {
  const params = new URLSearchParams({ q: query, page: String(page) });
  return `/search?${params.toString()}`;
}

function visiblePages(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (currentPage <= 3) {
    return [1, 2, 3, 4, "ellipsis", totalPages];
  }

  if (currentPage >= totalPages - 2) {
    return [1, "ellipsis", totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  }

  return [1, "ellipsis", currentPage - 1, currentPage, currentPage + 1, "ellipsis", totalPages];
}

export function Pagination({ query, currentPage, totalPages }: PaginationProps) {
  if (totalPages <= 1) {
    return null;
  }

  const previousPage = Math.max(1, currentPage - 1);
  const nextPage = Math.min(totalPages, currentPage + 1);

  return (
    <nav aria-label="Search results pages" className="flex items-center justify-between gap-4 py-8">
      {currentPage > 1 ? (
        <Link
          href={pageHref(query, previousPage)}
          className="inline-flex items-center gap-2 border-b border-ink pb-1 text-sm font-bold text-ink hover:border-cobalt hover:text-cobalt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
        >
          <ArrowLeftIcon />
          Previous
        </Link>
      ) : (
        <span className="inline-flex items-center gap-2 border-b border-transparent pb-1 text-sm font-bold text-muted/40" aria-disabled="true">
          <ArrowLeftIcon />
          Previous
        </span>
      )}

      <div className="flex items-center gap-1">
        {visiblePages(currentPage, totalPages).map((page, index) =>
          page === "ellipsis" ? (
            <span key={`ellipsis-${index}`} className="px-1 text-sm text-muted" aria-hidden="true">
              …
            </span>
          ) : (
            <Link
              key={page}
              href={pageHref(query, page)}
              aria-current={page === currentPage ? "page" : undefined}
              className={`grid h-9 min-w-9 place-items-center px-2 text-sm font-bold tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-2 ${
                page === currentPage
                  ? "bg-ink text-paper-raised"
                  : "text-ink hover:bg-cobalt-soft hover:text-cobalt-deep"
              }`}
            >
              {page}
            </Link>
          ),
        )}
      </div>

      {currentPage < totalPages ? (
        <Link
          href={pageHref(query, nextPage)}
          className="inline-flex items-center gap-2 border-b border-ink pb-1 text-sm font-bold text-ink hover:border-cobalt hover:text-cobalt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
        >
          Next
          <ArrowRightIcon />
        </Link>
      ) : (
        <span className="inline-flex items-center gap-2 border-b border-transparent pb-1 text-sm font-bold text-muted/40" aria-disabled="true">
          Next
          <ArrowRightIcon />
        </span>
      )}
    </nav>
  );
}
