import { useCallback, useEffect, useMemo, useState } from "react";
import { Github } from "lucide-react";
import { SearchPalette } from "./components/SearchPalette";
import { MappingDetail } from "./components/MappingDetail";
import { type Channel } from "./lib/api";
import { useDerivedIndex, type Side, type SearchHit } from "./lib/names";

interface Selection {
  side: Side;
  name: string;
}

const EXAMPLES = [
  "numpy",
  "requests",
  "arm-pyart",
  "flask",
  "scikit-learn",
  "pillow",
];

function readUrl(): {
  channel: Channel;
  query: string;
  selection: Selection | null;
} {
  const params = new URLSearchParams(window.location.search);
  const channel: Channel =
    params.get("channel") === "bioconda" ? "bioconda" : "conda-forge";
  const query = params.get("q") ?? "";
  const dir = params.get("dir");
  const selection: Selection | null =
    query && (dir === "conda" || dir === "pypi")
      ? { side: dir, name: query }
      : null;
  return { channel, query, selection };
}

function writeUrl(channel: Channel, selection: Selection | null) {
  const params = new URLSearchParams();
  if (channel !== "conda-forge") params.set("channel", channel);
  if (selection) {
    params.set("q", selection.name);
    params.set("dir", selection.side);
  }
  const search = params.toString();
  const url = `${window.location.pathname}${search ? `?${search}` : ""}`;
  window.history.replaceState(null, "", url);
}

export default function App() {
  const initial = readUrl();
  const [channel, setChannel] = useState<Channel>(initial.channel);
  const [query, setQuery] = useState(initial.query);
  const [selection, setSelection] = useState<Selection | null>(
    initial.selection,
  );

  useEffect(() => {
    writeUrl(channel, selection);
  }, [channel, selection]);

  const handleSelect = useCallback((hit: SearchHit) => {
    setQuery(hit.name);
    setSelection({ side: hit.side, name: hit.name });
  }, []);

  const handleChannelChange = useCallback((next: Channel) => {
    setChannel(next);
    setSelection(null);
  }, []);

  const handleHome = useCallback(() => {
    setSelection(null);
    setQuery("");
  }, []);

  return (
    <div className="flex min-h-dvh flex-col">
      <div className="mx-auto flex w-full max-w-canvas flex-1 flex-col px-5 py-8 sm:px-10 sm:py-12">
        <header className="flex items-start justify-between gap-6">
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={handleHome}
              className="self-start cursor-pointer rounded-md font-display text-[44px] font-light leading-none tracking-[-0.015em] text-ink hover:text-ink-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label="parselmouth — back to home"
            >
              parselmouth
            </button>
            <p className="max-w-[54ch] text-base leading-snug text-cream-600">
              Browse the conda to pypi package name mapping.
            </p>
          </div>
          <a
            href="https://github.com/prefix-dev/parselmouth"
            target="_blank"
            rel="noreferrer"
            aria-label="View parselmouth on GitHub"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-rail bg-white text-ink"
          >
            <Github size={18} />
          </a>
        </header>

        <div className="mt-8">
          <SearchPalette
            channel={channel}
            onChannelChange={handleChannelChange}
            query={query}
            onQueryChange={setQuery}
            onSelect={handleSelect}
          />
        </div>

        <main className="mt-10 flex flex-col">
          {selection ? (
            <MappingDetail
              key={`${channel}:${selection.side}:${selection.name}`}
              channel={channel}
              side={selection.side}
              name={selection.name}
            />
          ) : (
            <EmptyHero
              channel={channel}
              query={query}
              onQueryChange={setQuery}
            />
          )}
        </main>
      </div>

      <Footer channel={channel} />
    </div>
  );
}

function EmptyHero({
  channel,
  query,
  onQueryChange,
}: {
  channel: Channel;
  query: string;
  onQueryChange: (q: string) => void;
}) {
  const { index } = useDerivedIndex(channel);

  const stats = useMemo(() => {
    if (!index)
      return {
        conda: null as number | null,
        pypi: null as number | null,
        mappedConda: null as number | null,
      };
    return {
      conda: index.condaCount,
      pypi: index.pypiCount,
      mappedConda: Object.keys(index.pairs).length,
    };
  }, [index]);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-rail bg-white p-8 shadow-card sm:px-9 sm:py-8">
        <h2 className="m-0 font-display text-[30px] font-light leading-tight text-ink">
          Search a package name.
        </h2>
        <p className="mt-2 text-sm text-cream-600">
          Press{" "}
          <kbd className="inline-flex items-center rounded-[5px] border border-b-2 border-rail bg-white px-1.5 py-0.5 font-mono text-[11px] font-medium leading-none text-cream-600">
            ⌘ K
          </kbd>{" "}
          or{" "}
          <kbd className="inline-flex items-center rounded-[5px] border border-b-2 border-rail bg-white px-1.5 py-0.5 font-mono text-[11px] font-medium leading-none text-cream-600">
            /
          </kbd>{" "}
          to focus.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="mr-1 font-sans text-2xs font-semibold uppercase tracking-eyebrow text-cream-600">
            try
          </span>
          {EXAMPLES.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={query === n}
              onClick={() => onQueryChange(n)}
              className="cursor-pointer rounded-lg border border-rail bg-white px-2.5 py-1 font-mono text-[12.5px] text-ink hover:bg-cream-100"
            >
              {n}
            </button>
          ))}
        </div>
      </section>
      <section className="rounded-2xl border border-rail bg-white p-2 shadow-card sm:px-9 sm:py-8">
        <div className="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
          <Stat n="hourly" showPound={false} label="pipeline refresh" />
          <Stat
            n={stats.conda?.toLocaleString() ?? "—"}
            label={`${channel} conda names`}
          />
          <Stat n={stats.pypi?.toLocaleString() ?? "—"} label="PyPI names" />
          <Stat
            n={stats.mappedConda?.toLocaleString() ?? "—"}
            label="mapped to PyPI"
          />
        </div>
      </section>
    </div>
  );
}

function Stat({
  n,
  label,
  hint,
  className,
  showPound = true,
}: {
  n: string;
  label: string;
  hint?: string;
  className?: string;
  showPound?: boolean;
}) {
  return (
    <div className={"flex min-w-0 flex-col " + (className ?? "")}>
      <div className="font-display text-3xl font-light leading-tight tracking-[-0.01em] text-ink">
        {showPound ? "# " : ""}
        {n}
      </div>
      <div className="mt-1 inline-flex items-center gap-1.5 font-sans text-[12.5px] font-medium text-ink">
        {label}
      </div>
      {hint && (
        <div className="mt-0.5 font-sans text-[11.5px] leading-snug text-cream-400">
          {hint}
        </div>
      )}
    </div>
  );
}

function Footer({ channel }: { channel: Channel }) {
  return (
    <footer className="mx-auto w-full max-w-canvas px-5 pb-8 sm:px-10">
      <div className="text-xs text-cream-400">
        Data from{" "}
        <code className="rounded bg-cream-100 px-1 py-px font-mono text-cream-600">
          conda-mapping.prefix.dev
        </code>
        , updated hourly by the parselmouth pipeline. Channel{" "}
        <code className="rounded bg-cream-100 px-1 py-px font-mono text-cream-600">
          {channel}
        </code>
        .
      </div>
    </footer>
  );
}
