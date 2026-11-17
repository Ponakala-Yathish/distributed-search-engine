import Link from "next/link";

interface EmptyStateProps {
  title: string;
  message: string;
}

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="border-y border-line py-14 text-center">
      <h2 className="text-2xl font-bold tracking-[-0.02em] text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-reading text-base leading-7 text-muted">{message}</p>
      <Link
        href="/"
        className="mt-6 inline-flex border-b-2 border-cobalt pb-1 text-sm font-bold text-cobalt hover:border-cobalt-deep"
      >
        Start a new search
      </Link>
    </div>
  );
}
