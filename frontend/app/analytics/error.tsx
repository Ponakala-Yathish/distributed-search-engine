"use client";

import { ErrorNotice } from "@/components/ui/error-notice";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-4xl px-5 py-12 sm:px-8 lg:px-12">
      <ErrorNotice title="Analytics could not be loaded" message="The request failed before it reached the search service." />
      <button
        type="button"
        onClick={reset}
        className="mt-6 border-b-2 border-cobalt pb-1 text-sm font-bold text-cobalt hover:border-cobalt-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
      >
        Try again
      </button>
    </div>
  );
}
