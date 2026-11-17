interface SignalProps {
  label: string;
  value: number;
  max: number;
}

export function Signal({ label, value, max }: SignalProps) {
  const percentage = max > 0 ? Math.max(1, Math.min(100, (value / max) * 100)) : 0;

  return (
    <div className="border-b border-line py-4 last:border-b-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-semibold text-muted">{label}</span>
        <span className="text-lg font-bold tabular-nums text-ink">{value.toLocaleString("en-US")}</span>
      </div>
      <div className="mt-3 h-px bg-line" aria-hidden="true">
        <div className="h-px bg-cobalt" style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}
