interface ErrorNoticeProps {
  title?: string;
  message?: string;
}

export function ErrorNotice({
  title = "The search service could not be reached",
  message = "Check that the API is running, then try the request again.",
}: ErrorNoticeProps) {
  return (
    <div className="border border-critical/40 bg-critical/5 p-5 sm:p-6" role="alert">
      <div className="flex items-start gap-4">
        <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-critical" aria-hidden="true" />
        <div>
          <h2 className="text-lg font-bold text-ink">{title}</h2>
          <p className="mt-1 max-w-reading text-sm leading-6 text-muted">{message}</p>
        </div>
      </div>
    </div>
  );
}
