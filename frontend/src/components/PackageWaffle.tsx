const PER_BLOCK = 500;

// A mapped package lives in both ecosystems, so its block is a diagonal split
// of conda-green and PyPI-blue (.ps-waffle-mapped). Conda-only blocks are a
// plain lighter green.
const MAPPED_BLOCK = "ps-waffle-mapped";

interface Props {
  channel: string;
  condaTotal: number | null;
  mapped: number | null;
  pypiNames: number | null;
}

/**
 * Isotype / waffle graphic for the empty-state hero: each block stands for
 * ~500 conda packages, colored to show how much of the channel is mapped to
 * PyPI. The grid size scales with the channel, so bioconda visibly renders a
 * smaller block than conda-forge.
 */
export function PackageWaffle({
  channel,
  condaTotal,
  mapped,
  pypiNames,
}: Props) {
  const loaded = condaTotal !== null && mapped !== null && pypiNames !== null;

  const totalBlocks = loaded
    ? Math.max(1, Math.round(condaTotal / PER_BLOCK))
    : 48;
  const mappedBlocks = loaded
    ? Math.min(totalBlocks, Math.round(mapped / PER_BLOCK))
    : 0;
  const condaOnly = loaded ? condaTotal - mapped : null;

  return (
    <div
      role="img"
      aria-label={
        loaded
          ? `${mapped.toLocaleString()} of ${condaTotal.toLocaleString()} ${channel} packages map to a PyPI name`
          : "Loading package counts"
      }
    >
      <div className="flex items-baseline gap-2">
        <span className="font-display text-base font-semibold text-cream-700">
          {channel}
        </span>
        <span className="font-sans text-2xs text-cream-400">
          each block ≈ {PER_BLOCK} packages
        </span>
      </div>

      <div
        className="mt-3 flex max-w-[20rem] flex-wrap gap-1"
        aria-hidden="true"
      >
        {Array.from({ length: totalBlocks }, (_, i) => (
          <span
            key={i}
            className={
              "h-4 w-4 rounded-[3px] shadow-sm " +
              (!loaded
                ? "bg-cream-200"
                : i < mappedBlocks
                  ? MAPPED_BLOCK
                  : "bg-conda-border")
            }
          />
        ))}
      </div>

      <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
        <WaffleLegend
          swatch={MAPPED_BLOCK}
          value={mapped}
          label="mapped to PyPI"
        />
        <WaffleLegend
          swatch="bg-conda-border"
          value={condaOnly}
          label="conda-only"
        />
      </div>
    </div>
  );
}

function WaffleLegend({
  swatch,
  value,
  label,
}: {
  swatch: string;
  value: number | null;
  label: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-2.5">
      <span
        className={`h-3.5 w-3.5 shrink-0 rounded-[3px] shadow-sm ${swatch}`}
      />
      <span className="flex flex-col">
        <span className="font-display text-2xl font-light leading-none tracking-[-0.01em] text-ink">
          {value?.toLocaleString() ?? "—"}
        </span>
        <span className="mt-1 font-sans text-[12px] text-cream-600">
          {label}
        </span>
      </span>
    </span>
  );
}
