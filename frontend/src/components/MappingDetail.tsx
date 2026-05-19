import { useMemo } from "react";
import { ExternalLink, Sparkles } from "lucide-react";
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
}

interface ListItem {
  name: string;
  context?: string;
  primary?: boolean;
}

export function MappingDetail({ channel, side, name }: Props) {
  const indexQuery = useDerivedIndex(channel);
  const index = indexQuery.index;
  const loading = indexQuery.isLoading;

  // We can't distinguish vendoring from historical drift in the pairs data
  // (both look like "this name maps to N other names"), so we just show the
  // list with the selected item flagged. No "direct"/"vendors" labels.
  const condaList: ListItem[] = useMemo(() => {
    if (!index)
      return side === "conda" ? [{ name, primary: true, context: "selected" }] : [];
    if (side === "conda") {
      return [{ name, primary: true, context: "selected" }];
    }
    const condaNames = lookupPypiToConda(index, normalizePypi(name));
    return condaNames.map((c, i) => ({
      name: c,
      primary: i === 0,
    }));
  }, [index, side, name]);

  const pypiList: ListItem[] = useMemo(() => {
    if (side === "pypi") {
      const normalized = normalizePypi(name);
      const showNorm = normalized !== name;
      return [
        { name: showNorm ? normalized : name, primary: true, context: "selected" },
      ];
    }
    if (!index) return [];
    const pys = lookupCondaToPypi(index, name) ?? [];
    return pys.map((p, i) => ({ name: p, primary: i === 0 }));
  }, [index, side, name]);

  const primaryPypi =
    side === "pypi" ? normalizePypi(name) : pypiList[0]?.name ?? null;
  const primaryConda = side === "conda" ? name : condaList[0]?.name ?? null;

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
    <div className="flex min-h-0 flex-1 flex-col gap-5">
      <div className="flex items-center gap-3 text-sm text-cream-600">
        <span className="font-sans text-2xs font-semibold uppercase tracking-eyebrow text-cream-600">
          selection
        </span>
        <span className="font-mono text-sm text-ink">{name}</span>
        <SideBadge kind={side} />
        <span className="ml-auto hidden font-mono text-[11.5px] text-cream-400 md:inline-block">
          ?channel={channel}&q={name}&dir={side}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <PackageCard
          kind="conda"
          items={condaList}
          loading={loading && side === "pypi"}
          hrefFor={(n) => condaPackageUrl(channel, n)}
          emptyHint={
            side === "pypi" ? "No conda packages ship this PyPI name yet." : undefined
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
          <div className="font-sans text-[13.5px] font-semibold text-ink">
            No PyPI version detail available
          </div>
          <p className="mt-1.5 max-w-[60ch] leading-relaxed">
            This conda package has no PyPI mapping recorded — there's nothing
            to look up.
          </p>
        </div>
      )}
    </div>
  );
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
  hrefFor: (name: string) => string;
}

function PackageCard({
  kind,
  items,
  loading,
  normalized,
  emptyHint,
  hrefFor,
}: PackageCardProps) {
  const title = kind === "conda" ? "Conda packages" : "PyPI packages";
  const head =
    kind === "conda"
      ? "border-b-conda-border bg-conda-bg-soft text-conda-ink"
      : "border-b-pypi-border bg-pypi-bg-soft text-pypi-ink";

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
      <div className="px-2 py-1.5">
        {loading && (
          <div className="px-2.5 py-2 text-[13px] text-cream-600">Loading…</div>
        )}
        {!loading && items.length === 0 && (
          <div className="px-2.5 py-2 text-[13px] text-cream-600">
            {emptyHint ?? "—"}
          </div>
        )}
        {items.map((item, i) => (
          <a
            key={item.name}
            href={hrefFor(item.name)}
            target="_blank"
            rel="noreferrer"
            className={
              "group flex items-center gap-2.5 rounded-md px-2.5 py-2 font-mono text-[13.5px] tracking-[-0.01em] no-underline hover:bg-cream-50 " +
              (item.primary ? "text-ink font-medium" : "text-ink") +
              (i > 0 ? " border-t border-dashed border-rail" : "")
            }
          >
            <span className="w-3.5 text-right font-mono text-[11px] text-cream-400">
              {i + 1}
            </span>
            <span>{item.name}</span>
            <ExternalLink
              size={12}
              className="text-cream-300 opacity-0 transition-opacity group-hover:opacity-100"
            />
            {item.context && (
              <span className="ml-auto font-mono text-[11.5px] text-cream-400">
                {item.context}
              </span>
            )}
          </a>
        ))}
        {normalized && (
          <div className="px-2.5 pb-1 pt-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-rail bg-cream-100 px-2 py-0.5 text-[11.5px] text-cream-600">
              <Sparkles size={12} />
              normalized: <code className="font-mono text-[11px] text-ink">{normalized.from}</code> →{" "}
              <code className="font-mono text-[11px] text-ink">{normalized.to}</code>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
