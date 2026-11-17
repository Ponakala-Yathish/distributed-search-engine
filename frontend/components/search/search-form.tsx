import { SearchIcon } from "@/components/icons";

interface SearchFormProps {
  defaultValue?: string;
  compact?: boolean;
  label?: string;
}

export function SearchForm({
  defaultValue = "",
  compact = false,
  label = "Search documents",
}: SearchFormProps) {
  return (
    <form action="/search" method="get" role="search" className="w-full">
      <label htmlFor={compact ? "compact-search" : "hero-search"} className="sr-only">
        {label}
      </label>
      <div
        className={`flex items-stretch border border-ink bg-paper-raised transition-shadow focus-within:shadow-[0_0_0_3px_rgba(41,72,212,0.18)] ${
          compact ? "min-h-11" : "min-h-14 sm:min-h-16"
        }`}
      >
        <span className={`grid place-items-center border-r border-line text-muted ${compact ? "w-12" : "w-14 sm:w-16"}`}>
          <SearchIcon className={compact ? "h-4 w-4" : "h-5 w-5"} />
        </span>
        <input
          id={compact ? "compact-search" : "hero-search"}
          name="q"
          type="search"
          defaultValue={defaultValue}
          placeholder={compact ? "Search the index" : "Search by topic, phrase, or document"}
          autoComplete="off"
          className={`min-w-0 flex-1 bg-transparent px-4 text-ink outline-none placeholder:text-muted/80 ${
            compact ? "text-base" : "text-lg sm:text-xl"
          }`}
        />
        <button
          type="submit"
          className={`bg-ink px-5 font-bold text-paper-raised transition-colors hover:bg-cobalt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cobalt ${
            compact ? "text-sm" : "text-base sm:px-8"
          }`}
        >
          Search
        </button>
      </div>
    </form>
  );
}
