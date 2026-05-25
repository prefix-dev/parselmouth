import { useMemo, useState } from "react";
import { distance as levenshteinDistance } from "fastest-levenshtein";
import { Check, ChevronDown, ExternalLink, PackagePlus, Sparkles } from "lucide-react";
import { type Channel } from "../lib/api";
import {
  lookupCondaToPypi,
  lookupPypiToConda,
  useDerivedIndex,
  type Side,
} from "../lib/names";
import { normalizePypi } from "../lib/pypi";
import { condaPackageUrl, pypiPackageUrl } from "../lib/urls";
import { VersionHistory } from "./VersionHistory";
import { SideLogo } from "./Logos";

interface Props {
  channel: Channel;
  side: Side;
  name: string;
  isInPixiMapping?: boolean;
  onAddToPixiMapping?: (condaName: string) => void;
}

interface ListItem {
  name: string;
  context?: string;
  primary?: boolean;
}

export function MappingDetail({
  channel,
  side,
  name,
  isInPixiMapping,
  onAddToPixiMapping,
}: Props) {
  const indexQuery = useDerivedIndex(channel);
  const index = indexQuery.index;
  const loading = indexQuery.isLoading;

  // The PyPI name this selection resolves to. For a conda-side selection it is
  // the conda package's first mapped PyPI name; for a pypi-side selection it is
  // the normalized input.
  const primaryPypi = useMemo(() => {
    if (side === "pypi") return normalizePypi(name);
    if (!index) return null;
    return lookupCondaToPypi(index, name)?.[0] ?? null;
  }, [index, side, name]);

  // Conda card lists every conda package that maps to the same PyPI name, so
  // sibling packages (e.g. `pytorch` and `pytorch-cpu`, both mapping to
  // `torch`) all appear. The selected conda package is flagged.
  const condaList: ListItem[] = useMemo(() => {
    if (!index || !primaryPypi) {
      return side === "conda"
        ? [{ name, primary: true, context: "selected" }]
        : [];
    }
    const condaNames = lookupPypiToConda(index, primaryPypi);
    const directName = side === "conda" ? name : primaryPypi;
    const items = condaNames.map((c, i) => {
      const direct = c === directName;
      return {
        name: c,
        primary: direct || (side === "pypi" && i === 0 && !condaNames.includes(directName)),
        context:
          side === "conda" && direct
            ? "selected"
            : side === "pypi" && direct
              ? "name match"
              : undefined,
      };
    });

    // The reverse index is alphabetic by conda package name, which can bury the
    // best answer (e.g. pypi::numpy after hist-base). Keep exact selected/direct
    // matches first, then order the remaining observations by name similarity.
    return items.sort((a, b) => {
      const exactDelta = Number(b.name === directName) - Number(a.name === directName);
      if (exactDelta !== 0) return exactDelta;
      return nameDistance(a.name, directName) - nameDistance(b.name, directName);
    });
  }, [index, primaryPypi, side, name]);

  const pypiList: ListItem[] = useMemo(() => {
    if (side === "pypi") {
      const normalized = normalizePypi(name);
      const showNorm = normalized !== name;
      return [
        {
          name: showNorm ? normalized : name,
          primary: true,
          context: "selected",
        },
      ];
    }
    if (!index) return [];
    const pys = lookupCondaToPypi(index, name) ?? [];
    return pys.map((p, i) => ({ name: p, primary: i === 0 }));
  }, [index, side, name]);

  const primaryConda = side === "conda" ? name : (condaList[0]?.name ?? null);

  // PEP 503 normalization only: when the user's deep-linked PyPI input
  // differs from its canonical form (e.g. ?q=Foo_Bar → `foo-bar`), the
  // PyPI card shows the canonical name and this pill explains the swap.
  // Conda↔PyPI name differences (e.g. `pytorch` ↔ `torch`) are NOT
  // normalization — they're separate identifiers connected by a mapping,
  // and the two cards already show that side-by-side, so no pill needed.
  const normalized =
    side === "pypi" && normalizePypi(name) !== name
      ? { from: name, to: normalizePypi(name) }
      : null;

  return (
    <div className="flex flex-col gap-6 sm:gap-5">
      <div className="flex flex-col gap-3 text-sm text-cream-600 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          <span className="font-display text-lg font-semibold  text-cream-600">
            You've Selected:
          </span>
          <span className="font-display text-lg font-semibold text-ink">
            {name}
          </span>
          <SideBadge kind={side} />
        </div>
        {side === "conda" && primaryPypi && onAddToPixiMapping && (
          <button
            type="button"
            disabled={isInPixiMapping}
            onClick={() => onAddToPixiMapping(name)}
            className="inline-flex cursor-pointer items-center gap-1.5 self-start rounded-lg border border-conda-border bg-white px-2.5 py-1.5 text-xs font-semibold text-conda-ink hover:bg-conda-bg-soft disabled:cursor-default disabled:opacity-70 sm:ml-auto"
          >
            {isInPixiMapping ? <Check size={14} /> : <PackagePlus size={14} />}
            {isInPixiMapping ? "Added" : "Add to mapping"}
          </button>
        )}
      </div>

      <div className="grid gap-5 sm:grid-cols-2 sm:gap-4">
        <PackageCard
          kind="conda"
          items={condaList}
          loading={loading && side === "pypi"}
          hrefFor={(n) => condaPackageUrl(channel, n)}
          note={
            primaryPypi
              ? side === "conda"
                ? `Selected package, plus other packages that also report PyPI metadata for ${primaryPypi}.`
                : `Packages that report PyPI metadata for ${primaryPypi}.`
              : undefined
          }
          collapseSecondary
          secondaryLabel="other related conda packages"
          secondaryHint="These packages contain metadata for this PyPI name, but may just include it as a dependency or bundled file; they are not necessarily aliases."
          emptyHint={
            side === "pypi"
              ? "No conda packages ship this PyPI name yet."
              : undefined
          }
        />
        <PackageCard
          kind="pypi"
          items={pypiList}
          loading={loading && side === "conda"}
          normalized={normalized}
          hrefFor={(n) => pypiPackageUrl(n)}
          emptyHint={
            side === "conda"
              ? "No PyPI mapping recorded — likely conda-only."
              : undefined
          }
        />
      </div>

      {primaryPypi ? (
        <VersionHistory
          channel={channel}
          pypiName={primaryPypi}
          condaName={primaryConda}
        />
      ) : (
        <div className="px-1 pt-6 text-[13px] text-cream-600">
          <div className="font-display text-[13.5px] font-semibold text-ink">
            No PyPI version detail available
          </div>
          <p className="mt-1.5 max-w-[60ch] leading-relaxed">
            This conda package has no PyPI mapping recorded — there's nothing to
            look up.
          </p>
        </div>
      )}
    </div>
  );
}

function nameDistance(a: string, b: string): number {
  const left = normalizePackageName(a);
  const right = normalizePackageName(b);
  if (left === right) return 0;

  return levenshteinDistance(left, right) / Math.max(left.length, right.length, 1);
}

function normalizePackageName(name: string): string {
  return name.toLowerCase().replace(/[-_.]+/g, "-");
}

function SideBadge({ kind }: { kind: Side }) {
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

interface PackageCardProps {
  kind: "conda" | "pypi";
  items: ListItem[];
  loading?: boolean;
  normalized?: { from: string; to: string } | null;
  emptyHint?: string;
  note?: string;
  collapseSecondary?: boolean;
  secondaryLabel?: string;
  secondaryHint?: string;
  hrefFor: (name: string) => string;
}

function PackageCard({
  kind,
  items,
  loading,
  normalized,
  emptyHint,
  note,
  collapseSecondary,
  secondaryLabel = "other related packages",
  secondaryHint,
  hrefFor,
}: PackageCardProps) {
  const [secondaryOpen, setSecondaryOpen] = useState(false);
  const title = kind === "conda" ? "Conda packages" : "PyPI packages";
  const head =
    kind === "conda"
      ? "border-b-conda-border bg-conda-bg-soft text-conda-ink"
      : "border-b-pypi-border bg-pypi-bg-soft text-pypi-ink";

  const primaryItems = collapseSecondary ? items.filter((item) => item.primary) : items;
  const secondaryItems = collapseSecondary
    ? items.filter((item) => !item.primary)
    : [];
  const visibleItems = collapseSecondary
    ? secondaryOpen
      ? [...primaryItems, ...secondaryItems]
      : primaryItems
    : items;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-rail bg-white shadow-card">
      <div
        className={`flex items-center justify-between border-b px-4 py-3 ${head}`}
      >
        <div className="flex items-center gap-2 font-sans text-xs font-semibold uppercase tracking-[0.06em]">
          <SideLogo kind={kind} size={14} />
          {title}
        </div>
        <span className="font-mono text-[11.5px] text-cream-400">
          {items.length} {items.length === 1 ? "name" : "names"}
        </span>
      </div>
      {note && (
        <div className="border-b border-rail bg-cream-50 px-4 py-2 text-[12.5px] leading-relaxed text-cream-600">
          {note}
        </div>
      )}
      <div className="px-2 py-1.5">
        {loading && (
          <div className="px-2.5 py-2 text-[13px] text-cream-600">Loading…</div>
        )}
        {!loading && items.length === 0 && (
          <div className="px-2.5 py-2 text-[13px] text-cream-600">
            {emptyHint ?? "—"}
          </div>
        )}
        {visibleItems.map((item, i) => (
          <PackageRow
            key={item.name}
            item={item}
            index={i}
            href={hrefFor(item.name)}
          />
        ))}
        {collapseSecondary && secondaryItems.length > 0 && (
          <div className="border-t border-dashed border-rail px-2.5 py-2">
            <button
              type="button"
              onClick={() => setSecondaryOpen((open) => !open)}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md text-[12.5px] font-medium text-cream-600 hover:text-ink"
              aria-expanded={secondaryOpen}
            >
              <ChevronDown
                size={14}
                className={
                  "transition-transform " + (secondaryOpen ? "rotate-180" : "")
                }
              />
              {secondaryOpen ? "Hide" : "Show"} {secondaryItems.length} {secondaryLabel}
            </button>
            {secondaryHint && (
              <p className="mt-1.5 max-w-[48ch] text-[11.5px] leading-relaxed text-cream-500">
                {secondaryHint}
              </p>
            )}
          </div>
        )}
        {normalized && (
          <div className="px-2.5 pb-1 pt-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-rail bg-cream-100 px-2 py-0.5 text-[11.5px] text-cream-600">
              <Sparkles size={12} />
              normalized:{" "}
              <code className="font-mono text-[11px] text-ink">
                {normalized.from}
              </code>{" "}
              →{" "}
              <code className="font-mono text-[11px] text-ink">
                {normalized.to}
              </code>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function PackageRow({
  item,
  index,
  href,
}: {
  item: ListItem;
  index: number;
  href: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={
        "group flex items-center gap-2.5 rounded-md px-2.5 py-2 font-mono text-[13.5px] tracking-[-0.01em] no-underline hover:bg-cream-50 " +
        (item.primary ? "text-ink font-medium" : "text-ink") +
        (index > 0 ? " border-t border-dashed border-rail" : "")
      }
    >
      <span className="w-3.5 text-right font-mono text-[11px] text-cream-400">
        {index + 1}
      </span>
      <span>{item.name}</span>
      <ExternalLink
        size={12}
        className="text-cream-300 opacity-0 transition-opacity group-hover:opacity-100"
      />
      {item.context && (
        <span className="ml-auto rounded-full border border-rail bg-cream-50 px-1.5 py-0.5 font-sans text-[10.5px] font-semibold uppercase tracking-[0.05em] text-cream-600">
          {item.context}
        </span>
      )}
    </a>
  );
}
