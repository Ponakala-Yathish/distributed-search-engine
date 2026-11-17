import type { Metadata } from "next";
import Link from "next/link";

import { ArrowUpRightIcon, DocumentIcon } from "@/components/icons";
import { ErrorNotice } from "@/components/ui/error-notice";
import { getDocument } from "@/lib/api";
import { formatScore } from "@/lib/format";
import type { DocumentResponse } from "@/lib/types";

export const metadata: Metadata = {
  title: "Document",
};

export const dynamic = "force-dynamic";

interface DocumentPageProps {
  params: Promise<{ docId: string }>;
}

function documentTitle(document: DocumentResponse, documentId: string): string {
  return typeof document.title === "string" && document.title ? document.title : documentId;
}

function documentContent(document: DocumentResponse): string | null {
  if (typeof document.content === "string") {
    return document.content;
  }

  if (typeof document.text === "string") {
    return document.text;
  }

  return null;
}

async function loadDocument(docId: string): Promise<DocumentResponse | null> {
  try {
    return await getDocument(docId);
  } catch {
    return null;
  }
}

export default async function DocumentPage({ params }: DocumentPageProps) {
  const { docId } = await params;
  const document = await loadDocument(docId);

  if (!document) {
    return (
      <div className="mx-auto max-w-4xl px-5 py-12 sm:px-8 lg:px-12">
        <ErrorNotice
          title="The document could not be loaded"
          message="The document endpoint did not respond. Verify the document ID and try again."
        />
      </div>
    );
  }

  const title = documentTitle(document, docId);
  const content = documentContent(document);
  const url = typeof document.url === "string" ? document.url : null;
  const metadataEntries = document.metadata && typeof document.metadata === "object"
    ? Object.entries(document.metadata)
    : [];
  const scores = [
    { label: "Final", value: document.final_score },
    { label: "PageRank", value: document.pagerank_score },
  ].filter((score): score is { label: string; value: number } => typeof score.value === "number");

  return (
    <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14 lg:px-12">
      <Link
        href="/search"
        className="text-sm font-bold text-cobalt hover:text-cobalt-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
      >
        ← Back to search
      </Link>

      <header className="mt-7 grid gap-8 border-b border-ink pb-9 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <DocumentIcon className="h-7 w-7 text-cobalt" />
          <h1 className="mt-5 text-4xl font-bold leading-tight tracking-[-0.035em] sm:text-5xl">{title}</h1>
          <p className="mt-4 break-all font-mono text-sm text-muted">Document ID: {docId}</p>
        </div>
        <div className="lg:col-span-4 lg:border-l lg:border-line lg:pl-8">
          {scores.length > 0 ? (
            <dl className="space-y-4">
              {scores.map((score) => (
                <div key={score.label} className="flex items-baseline justify-between border-b border-line pb-3">
                  <dt className="text-sm font-semibold text-muted">{score.label} score</dt>
                  <dd className="text-xl font-bold tabular-nums">{formatScore(score.value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm leading-6 text-muted">No ranking scores are attached to this document.</p>
          )}
        </div>
      </header>

      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-cobalt hover:text-cobalt-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cobalt focus-visible:ring-offset-4"
        >
          Open source document
          <ArrowUpRightIcon />
        </a>
      ) : null}

      {typeof document.explanation === "string" && document.explanation ? (
        <section className="mt-10 border-l border-cobalt pl-5" aria-labelledby="ranking-explanation-heading">
          <h2 id="ranking-explanation-heading" className="text-xl font-bold tracking-[-0.02em]">
            Ranking explanation
          </h2>
          <p className="mt-2 max-w-reading leading-7 text-muted">{document.explanation}</p>
        </section>
      ) : null}

      {content ? (
        <section className="mt-10" aria-labelledby="document-content-heading">
          <h2 id="document-content-heading" className="text-xl font-bold tracking-[-0.02em]">
            Document content
          </h2>
          <div className="mt-4 whitespace-pre-wrap border-t border-line py-6 text-base leading-8 text-ink/85">
            {content}
          </div>
        </section>
      ) : null}

      {metadataEntries.length > 0 ? (
        <section className="mt-10" aria-labelledby="document-metadata-heading">
          <h2 id="document-metadata-heading" className="text-xl font-bold tracking-[-0.02em]">
            Metadata
          </h2>
          <dl className="mt-4 border-t border-line">
            {metadataEntries.map(([key, value]) => (
              <div key={key} className="grid gap-2 border-b border-line py-4 sm:grid-cols-3">
                <dt className="text-sm font-bold text-ink">{key.replace(/[_-]+/g, " ")}</dt>
                <dd className="text-sm leading-6 text-muted sm:col-span-2">
                  {typeof value === "object" ? JSON.stringify(value) : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </div>
  );
}
