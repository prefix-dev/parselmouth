import { useEffect, useMemo, useRef, useState } from "react";
import { Command } from "cmdk";
import { AlertCircle, Inbox, Loader2, Search } from "lucide-react";
import { useCompressedMapping, type Channel } from "../lib/api";
import { useNameSearcher, type SearchHit } from "../lib/names";
import { ChannelPopover } from "./ChannelPopover";
import { SideLogo } from "./Logos";

interface Props {
  channel: Channel;
  onChannelChange: (channel: Channel) => void;
  query: string;
  onQueryChange: (q: string) => void;
  onSelect: (hit: SearchHit) => void;
}

export function SearchPalette({
  channel,
  onChannelChange,
  query,
  onQueryChange,
  onSelect,
}: Props) {
  const mappingQuery = useCompressedMapping(channel);
  const searcher = useNameSearcher(channel);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (document.activeElement?.tagName ?? "").toLowerCase();
      const inField = tag === "input" || tag === "textarea";
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
        return;
      }
      if (e.key === "/" && !inField) {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const trimmed = query.trim();
  const hits = useMemo(() => searcher?.search(trimmed, 30) ?? [], [searcher, trimmed]);

  const loading = mappingQuery.isLoading;
  const error = mappingQuery.error;
  const indexCount = searcher ? searcher.condaCount + searcher.pypiCount : 0;

  const dropdownState: "results" | "empty" | "error" | "hidden" = !open
    ? "hidden"
    : error
    ? "error"
    : trimmed === ""
    ? "hidden"
    : hits.length === 0 && !loading
    ? "empty"
    : "results";

  return (
    <div ref={wrapRef} className="relative">
      <Command shouldFilter={false}>
        <div
          className={
            "relative flex h-14 items-stretch rounded-xl border border-rail bg-white transition-all focus-within:border-pypi-dot focus-within:ring-[3px] focus-within:ring-focus " +
            (loading ? "bg-cream-100" : "")
          }
        >
          <ChannelPopover value={channel} onChange={onChannelChange} />
          <span className="flex shrink-0 items-center pl-4 pr-3 text-cream-400">
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Search size={16} />
            )}
          </span>
          <Command.Input
            ref={inputRef}
            value={query}
            onValueChange={(v) => {
              onQueryChange(v);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder={
              loading ? "Loading mapping index…" : "numpy, requests, arm-pyart…"
            }
            disabled={loading || !!error}
            className="min-w-0 flex-1 border-0 bg-transparent font-mono text-[15px] tracking-[-0.01em] text-ink outline-none placeholder:text-cream-400 disabled:opacity-70"
          />
          <kbd className="mr-3.5 hidden self-center whitespace-nowrap rounded-[5px] border border-b-2 border-rail bg-white px-1.5 py-0.5 font-mono text-[11px] font-medium leading-none text-cream-600 sm:inline-flex">
            ⌘K
          </kbd>
        </div>

        {dropdownState !== "hidden" && (
          <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-30 overflow-hidden rounded-xl border border-rail bg-white shadow-dropdown">
          <Command.List className="max-h-[420px] overflow-y-auto">
            {dropdownState === "error" && (
              <div className="flex items-start gap-3 border-b border-error-border bg-error-bg px-4 py-3">
                <AlertCircle
                  size={16}
                  className="mt-0.5 shrink-0 text-error-accent"
                />
                <div>
                  <div className="text-[13px] font-semibold text-error-ink">
                    Failed to load mapping index
                  </div>
                  <div className="mt-0.5 font-mono text-xs text-error-ink">
                    {String(error)}
                  </div>
                  <button
                    type="button"
                    onClick={() => mappingQuery.refetch()}
                    className="mt-2 cursor-pointer rounded-lg border border-error-border bg-white px-2.5 py-1 text-xs font-medium text-error-ink"
                  >
                    Retry
                  </button>
                </div>
              </div>
            )}

            {dropdownState === "empty" && (
              <Command.Empty>
                <div className="px-4 py-7 text-center">
                  <Inbox size={22} className="mx-auto text-cream-400" />
                  <div className="mt-2 font-mono text-[13px] text-ink">
                    No matches for{" "}
                    <span className="text-ink">"{trimmed}"</span>
                  </div>
                  <div className="mt-1 text-xs text-cream-600">
                    Try a substring, or switch channel.
                  </div>
                </div>
              </Command.Empty>
            )}

            {dropdownState === "results" && (
              <>
                <div className="py-1.5">
                  <div className="px-3.5 pt-1.5 pb-1 font-sans text-[10.5px] font-semibold uppercase tracking-tracker text-cream-400">
                    Matches · {hits.length}
                  </div>
                  {hits.map((hit) => (
                    <Command.Item
                      key={`${hit.side}:${hit.name}`}
                      value={`${hit.side}:${hit.name}`}
                      onSelect={() => {
                        onSelect(hit);
                        setOpen(false);
                      }}
                      className="flex cursor-pointer items-center gap-2.5 px-3.5 py-2 font-mono text-sm tracking-[-0.01em] text-ink aria-selected:bg-cream-100"
                    >
                      <span className="font-mono">
                        <HighlightedName name={hit.name} query={trimmed} />
                      </span>
                      <span className="ml-auto inline-flex gap-1.5">
                        <Badge kind={hit.side} />
                      </span>
                    </Command.Item>
                  ))}
                </div>
                <div className="flex items-center justify-between border-t border-rail px-3.5 py-1.5">
                  <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-cream-400">
                    <Kbd>↵</Kbd> select <Sep />
                    <Kbd>↑</Kbd>
                    <Kbd>↓</Kbd> nav <Sep />
                    <Kbd>esc</Kbd> close
                  </span>
                  <span className="text-[11px] text-cream-400">
                    {channel} · {indexCount.toLocaleString()} names indexed
                  </span>
                </div>
              </>
            )}
          </Command.List>
          </div>
        )}
      </Command>
    </div>
  );
}

function HighlightedName({ name, query }: { name: string; query: string }) {
  if (!query) return <>{name}</>;
  const i = name.toLowerCase().indexOf(query.toLowerCase());
  if (i < 0) return <>{name}</>;
  return (
    <>
      {name.slice(0, i)}
      <mark>{name.slice(i, i + query.length)}</mark>
      {name.slice(i + query.length)}
    </>
  );
}

function Badge({ kind }: { kind: "conda" | "pypi" }) {
  const tones =
    kind === "conda"
      ? "border-conda-border bg-conda-bg text-conda-ink"
      : "border-pypi-border bg-pypi-bg text-pypi-ink";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 font-sans text-[11px] font-semibold lowercase leading-snug tracking-[0.02em] ${tones}`}
    >
      <SideLogo kind={kind} size={12} />
      {kind}
    </span>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center rounded-[5px] border border-b-2 border-rail bg-white px-1.5 py-0.5 font-mono text-[11px] font-medium leading-none text-cream-600">
      {children}
    </kbd>
  );
}

function Sep() {
  return <span aria-hidden="true">·</span>;
}
