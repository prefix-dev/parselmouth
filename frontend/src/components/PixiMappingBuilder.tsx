import { useState } from "react";
import {
  AlertCircle,
  Download,
  HelpCircle,
  Loader2,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";
import { type Channel, useCompressedMapping } from "../lib/api";
import {
  buildPixiMappingJson,
  closestMappedName,
  downloadPixiMapping,
  pixiMappingFilename,
  type PixiMappingCartItem,
} from "../lib/pixiMappingCart";
import { SideLogo } from "./Logos";

interface Props {
  channel: Channel;
  items: PixiMappingCartItem[];
  onRemove: (condaName: string) => void;
  onClear: () => void;
}

export function PixiMappingBuilder({
  channel,
  items,
  onRemove,
  onClear,
}: Props) {
  const [showHelp, setShowHelp] = useState(false);
  const mappingQuery = useCompressedMapping(channel);
  const mapping = mappingQuery.data;
  const exportJson = mapping ? buildPixiMappingJson(items, mapping) : null;
  const exportCount = exportJson ? Object.keys(exportJson).length : 0;
  const filename = pixiMappingFilename(channel);
  const snippet = `conda-pypi-map = { "${channel}" = "./${filename}" }`;
  const canDownload =
    !!exportJson && exportCount === items.length && items.length > 0;

  return (
    <section className="rounded-2xl border border-rail bg-white shadow-card">
      <div className="flex flex-col gap-3 border-b border-rail px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 font-display text-lg font-semibold text-ink">
            <WandSparkles size={18} /> Pixi Mapping Builder
          </div>
          <p className="mt-1 text-xs text-cream-600">
            Use this tool to create a custom <code>conda-pypi-map</code> for{" "}
            {channel}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-rail bg-cream-100 px-2.5 py-1 font-mono text-[11px] text-cream-600">
            {items.length} {items.length === 1 ? "package" : "packages"}
          </span>
          <button
            type="button"
            onClick={() => setShowHelp((show) => !show)}
            aria-expanded={showHelp}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-rail bg-white px-2.5 py-1.5 text-xs font-medium text-cream-600 hover:bg-cream-50"
          >
            <HelpCircle size={13} /> Help
          </button>
          <button
            type="button"
            onClick={onClear}
            disabled={items.length === 0}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-rail bg-white px-2.5 py-1.5 text-xs font-medium text-cream-600 hover:bg-cream-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 size={13} /> Clear
          </button>
          <button
            type="button"
            onClick={() =>
              exportJson && downloadPixiMapping(channel, exportJson)
            }
            disabled={!canDownload}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-ink bg-ink px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-ink-deep disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={13} /> Download
          </button>
        </div>
      </div>

      {showHelp && <PixiMappingHelp channel={channel} />}

      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.75fr)]">
        <div className="overflow-hidden rounded-xl border border-rail">
          {items.length === 0 ? (
            <div className="px-4 py-6 text-sm text-cream-600">
              No packages added yet. Use{" "}
              <span className="font-medium text-ink">Add to mapping</span> on
              conda package results.
            </div>
          ) : (
            <div className="divide-y divide-rail">
              {items.map((item) => {
                const pypiNames = mapping?.[item.condaName];
                const mappedName = closestMappedName(item.condaName, pypiNames);
                const isNull = mapping && !mappedName;
                return (
                  <div
                    key={item.condaName}
                    className="grid gap-2 px-3 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto] sm:items-center"
                  >
                    <div className="min-w-0 font-mono text-[13px] text-ink">
                      <span className="mr-2 inline-flex align-middle">
                        <SideLogo kind="conda" size={13} />
                      </span>
                      <span className="break-all">{item.condaName}</span>
                    </div>
                    <span className="hidden text-cream-400 sm:block">→</span>
                    <div className="min-w-0">
                      {mappingQuery.isLoading ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-cream-600">
                          <Loader2 size={12} className="animate-spin" />{" "}
                          resolving…
                        </span>
                      ) : mappingQuery.error ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-error-ink">
                          <AlertCircle size={12} /> mapping unavailable
                        </span>
                      ) : isNull ? (
                        <span className="rounded-md border border-error-border bg-error-bg px-1.5 py-0.5 font-mono text-[12px] text-error-ink">
                          no PyPI mapping · remove to download
                        </span>
                      ) : (
                        <span className="font-mono text-[13px] text-pypi-ink">
                          <span className="mr-2 inline-flex align-middle">
                            <SideLogo kind="pypi" size={13} />
                          </span>
                          {mappedName}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemove(item.condaName)}
                      aria-label={`Remove ${item.condaName} from Pixi mapping`}
                      className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border border-rail bg-white text-cream-500 hover:bg-cream-50 hover:text-ink"
                    >
                      <X size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 rounded-xl border border-rail bg-cream-50 p-3">
          <div>
            <div className="font-display text-base font-semibold text-ink">
              pixi.toml
            </div>
            <pre className="mt-1 overflow-x-auto rounded-lg border border-rail bg-white p-2 font-mono text-[12px] text-ink">
              {snippet}
            </pre>
          </div>
          {mappingQuery.error ? (
            <div className="rounded-lg border border-error-border bg-error-bg p-2 text-xs text-error-ink">
              Failed to load the source mapping. Retry before downloading.
              <button
                type="button"
                onClick={() => mappingQuery.refetch()}
                className="mt-2 block cursor-pointer rounded-md border border-error-border bg-white px-2 py-1 font-medium"
              >
                Retry
              </button>
            </div>
          ) : (
            <p className="text-xs leading-relaxed text-cream-600">
              The download uses Pixi's single-name JSON shape. If Parselmouth
              has multiple PyPI names for a conda package, the closest name by
              edit distance is used.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function PixiMappingHelp({ channel }: { channel: Channel }) {
  return (
    <div className="border-b border-rail bg-cream-50 px-4 py-4">
      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <h3 className="font-display text-base font-semibold text-ink">
            What this builds
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-cream-600">
            This creates a small Pixi <code>conda-pypi-map</code> JSON file for
            the current <span className="font-medium text-ink">{channel}</span>{" "}
            channel. Pixi can use it offline instead of fetching the default
            package-name mapping.
          </p>
        </div>
        <div>
          <h3 className="font-display text-base font-semibold text-ink">
            What to add
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-cream-600">
            Add conda packages that have a known PyPI name. Packages without a
            PyPI mapping are intentionally not addable because Pixi expects the
            downloaded file to contain usable conda-to-PyPI entries.
          </p>
        </div>
        <div>
          <h3 className="font-display text-base font-semibold text-ink">
            How to use it
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-cream-600">
            Download the JSON file, commit it with your project, then paste the
            shown <code>conda-pypi-map</code> line into <code>pixi.toml</code>.
            If a package has multiple PyPI names, the closest name by edit
            distance is exported.
          </p>
        </div>
      </div>
    </div>
  );
}
