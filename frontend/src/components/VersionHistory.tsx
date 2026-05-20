import { useMemo } from "react";
import { AlertCircle, Box, ExternalLink, Loader2 } from "lucide-react";
import { condaNamesFor, usePypiDetail, type Channel } from "../lib/api";
import { normalizePypi } from "../lib/pypi";
import { condaPackageUrl, pypiPackageUrl, pypiVersionUrl } from "../lib/urls";
import { CondaLogo, PypiLogo } from "./Logos";

interface Props {
  channel: Channel;
  /** The selected PyPI name — the row key for the v1 lookup. */
  pypiName: string | null;
  /** The conda name to display in the header line. May differ from the value column when drift exists. */
  condaName: string | null;
}

interface Row {
  pypiVersion: string;
  conda: string[];
}

export function VersionHistory({
  channel,
  pypiName,
  condaName,
}: Props) {
  const detail = usePypiDetail(channel, pypiName);
  const normalizedPypi = pypiName ? normalizePypi(pypiName) : null;

  const rows: Row[] = useMemo(() => {
    if (!detail.data) return [];
    return Object.entries(detail.data.conda_versions)
      .map(([pypiVersion, value]) => ({
        pypiVersion,
        conda: condaNamesFor(value),
      }))
      .sort((a, b) =>
        b.pypiVersion.localeCompare(a.pypiVersion, undefined, {
          numeric: true,
        }),
      );
  }, [detail.data]);

  const items = useMemo(() => {
    const out: Array<
      | { kind: "row"; row: Row }
      | { kind: "drift"; from: Row; to: Row }
    > = [];
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      const prev = rows[i - 1];
      if (prev && r.conda.join(",") !== prev.conda.join(",")) {
        out.push({ kind: "drift", from: prev, to: r });
      }
      out.push({ kind: "row", row: r });
    }
    return out;
  }, [rows]);

  const headerCondaName = condaName ?? rows[0]?.conda[0] ?? "—";
  const headerPypiName = pypiName ?? "—";

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-end justify-between gap-4 border-b border-rail px-1 py-3 flex-shrink-0">
        <div className="flex flex-col gap-1">
          <span className="font-sans text-2xs font-semibold uppercase tracking-eyebrow text-cream-600">
            Version history
          </span>
          <span className="inline-flex items-center gap-2 font-mono text-sm leading-tight text-ink">
            <span className="inline-flex items-center gap-1.5">
              <CondaLogo size={14} />
              <a
                href={condaPackageUrl(channel, headerCondaName)}
                target="_blank"
                rel="noreferrer"
                className="hover:underline"
              >
                {headerCondaName}
              </a>
            </span>
            <span aria-hidden="true" className="text-cream-400">
              ↔
            </span>
            <span className="inline-flex items-center gap-1.5">
              <PypiLogo size={14} />
              <a
                href={pypiPackageUrl(headerPypiName)}
                target="_blank"
                rel="noreferrer"
                className="hover:underline"
              >
                {headerPypiName}
              </a>
            </span>
          </span>
        </div>
        <div className="inline-flex flex-wrap items-center justify-end gap-2.5 text-xs text-cream-600">
          {detail.isLoading && <StateChip label="Loading" tone="loading" />}
          {detail.error && <StateChip label="Error" tone="error" />}
          {detail.data && rows.length === 0 && (
            <StateChip label="No data" tone="empty" />
          )}
          {detail.data && rows.length > 0 && (
            <>
              <span className="font-mono">
                {rows.length} {rows.length === 1 ? "release" : "releases"}
              </span>
              <span className="text-cream-400" aria-hidden="true">·</span>
              <a
                className="inline-flex items-center gap-1.5 text-cream-600 hover:text-pypi-dot"
                href={`https://conda-mapping.prefix.dev/pypi-to-conda-v1/${channel}/${normalizedPypi}.json`}
                target="_blank"
                rel="noreferrer"
              >
                <span className="font-mono">
                  pypi-to-conda-v1/{channel}/{normalizedPypi}.json
                </span>
                <ExternalLink size={12} className="text-cream-400" />
              </a>
            </>
          )}
        </div>
      </header>

      {detail.isLoading && <LoadingSkeleton name={headerCondaName} />}
      {detail.error && (
        <ErrorState
          channel={channel}
          name={headerCondaName}
          message={String(detail.error)}
          onRetry={() => detail.refetch()}
        />
      )}
      {detail.data && rows.length === 0 && (
        <EmptyState channel={channel} name={headerCondaName} />
      )}

      {detail.data && rows.length > 0 && (
        <>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-rail">
          <div className="ps-scroll min-h-0 flex-1 overflow-y-auto">
          <table className="w-full border-collapse font-mono text-[13px]">
            <thead>
              <tr>
                <Th className="w-[28%]">pypi version</Th>
                <Th className="w-[72%]">conda name</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, i) =>
                it.kind === "drift" ? (
                  <DriftRow key={`d-${i}`} from={it.from} to={it.to} />
                ) : (
                  <TableRow
                    key={`r-${i}-${it.row.pypiVersion}`}
                    row={it.row}
                    channel={channel}
                    pypiName={headerPypiName}
                  />
                ),
              )}
            </tbody>
          </table>
          </div>
        </div>
        <p className="mt-2 flex-shrink-0 px-1 text-[11.5px] text-cream-400">
          Only releases with a known PyPI mapping are shown. Conda releases
          without a known PyPI counterpart aren't surfaced by the parselmouth
          v1 endpoint.
        </p>
        </>
      )}
    </section>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={
        "sticky top-0 z-10 border-b border-rail bg-cream-100 px-4 py-2.5 text-left font-sans text-2xs font-semibold uppercase tracking-tracker text-cream-700 " +
        className
      }
    >
      {children}
    </th>
  );
}

function TableRow({
  row,
  channel,
  pypiName,
}: {
  row: Row;
  channel: Channel;
  pypiName: string;
}) {
  return (
    <tr className="border-b border-rail last:border-b-0 odd:bg-white even:bg-cream-50/60 hover:bg-cream-100/70">
      <td className="border-r border-rail px-4 py-2 font-mono font-medium tabular-nums text-ink">
        <a
          href={pypiVersionUrl(pypiName, row.pypiVersion)}
          target="_blank"
          rel="noreferrer"
          className="hover:underline"
        >
          {row.pypiVersion}
        </a>
      </td>
      <td className="px-4 py-2 font-mono text-conda-ink">
        {row.conda.map((c, i) => (
          <span key={c}>
            {i > 0 && <span className="text-cream-400">, </span>}
            <a
              href={condaPackageUrl(channel, c)}
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              {c}
            </a>
          </span>
        ))}
      </td>
    </tr>
  );
}

function DriftRow({ from, to }: { from: Row; to: Row }) {
  const fromConda = from.conda.join(", ");
  const toConda = to.conda.join(", ");
  return (
    <tr className="border-b border-rail bg-brand-yellow/10">
      <td colSpan={2} className="px-4 py-1.5">
        <span className="inline-flex items-center gap-1.5">
          <span className="font-sans text-[9px] font-semibold uppercase tracking-eyebrow text-cream-700">
            conda name changed
          </span>
          <span className="font-mono text-[11.5px] text-cream-500 line-through decoration-cream-400">
            {fromConda}
          </span>
          <span className="text-cream-400">→</span>
          <span className="font-mono text-[11.5px] font-medium text-ink">
            {toConda}
          </span>
        </span>
      </td>
    </tr>
  );
}

function LoadingSkeleton({ name }: { name: string }) {
  const widths = [60, 48, 64, 52, 70, 58];
  return (
    <div className="px-1 pb-2 pt-6 text-[13px] text-cream-600">
      <div className="flex items-center gap-2">
        <Loader2 size={16} className="animate-spin" />
        Loading version history for <span className="font-mono">{name}</span>…
      </div>
      <div className="mt-3 space-y-1.5">
        {widths.map((w, i) => (
          <div key={i} className="flex gap-4 py-1.5">
            <span className="inline-block h-3 w-14 rounded bg-cream-100" />
            <span
              className="inline-block h-3 rounded bg-cream-100"
              style={{ width: `${w}%` }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function ErrorState({
  name,
  channel,
  message,
  onRetry,
}: {
  name: string;
  channel: Channel;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex items-start gap-3.5 px-1 py-7">
      <AlertCircle size={20} className="mt-0.5 shrink-0 text-error-accent" />
      <div>
        <div className="font-sans text-[13.5px] font-semibold text-ink">
          Couldn't load version history
        </div>
        <p className="mt-1.5 max-w-[60ch] text-[13px] leading-relaxed text-cream-600">
          The pipeline hasn't published a mapping for{" "}
          <span className="font-mono">{name}</span> on{" "}
          <span className="font-mono">{channel}</span>, or the request was
          blocked. This usually means the package was vendored without a direct
          conda alias, the next pipeline run hasn't completed, or CORS isn't
          yet enabled on the conda-mapping.prefix.dev bucket.
        </p>
        <p className="mt-1.5 max-w-[60ch] font-mono text-[11px] text-cream-400">
          {message}
        </p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={onRetry}
            className="cursor-pointer rounded-lg border border-rail bg-white px-3 py-1 text-[12.5px] font-medium text-ink"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ name, channel }: { name: string; channel: Channel }) {
  return (
    <div className="flex items-start gap-3.5 px-1 py-7">
      <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-cream-100 text-cream-600">
        <Box size={18} />
      </div>
      <div>
        <div className="font-sans text-[13.5px] font-semibold text-ink">
          No version mapping for <span className="font-mono">{name}</span>
        </div>
        <p className="mt-1.5 max-w-[60ch] text-[13px] leading-relaxed text-cream-600">
          This package may be conda-only on{" "}
          <span className="font-mono">{channel}</span>, with no PyPI release
          history to map.
        </p>
      </div>
    </div>
  );
}

function StateChip({
  label,
  tone,
}: {
  label: string;
  tone: "loading" | "error" | "empty";
}) {
  const palette = {
    loading: "border-warning-border bg-warning-bg text-warning-ink",
    error: "border-error-border bg-error-bg text-error-ink",
    empty: "border-rail bg-cream-100 text-cream-600",
  }[tone];
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-full border px-1.5 py-0.5 font-mono text-2xs uppercase tracking-[0.06em] " +
        palette
      }
    >
      {label}
    </span>
  );
}
