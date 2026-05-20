import * as Dialog from "@radix-ui/react-dialog";
import { CircleHelp, X } from "lucide-react";

/**
 * Header "How it works" dialog: a quick conceptual explanation of how the
 * conda <-> PyPI mapping is derived, aimed at pixi users.
 */
export function HowItWorks() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button
          type="button"
          aria-label="How it works"
          className="inline-flex h-9 w-9 items-center justify-center gap-1.5 rounded-xl border border-rail bg-white font-sans text-sm text-ink hover:bg-cream-100 sm:w-auto sm:px-3"
        >
          <CircleHelp size={15} className="text-cream-500" />
          <span className="hidden sm:inline">How it works</span>
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-[calc(100vw-2rem)] max-w-[900px] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-rail bg-white p-6 shadow-dropdown focus:outline-none sm:p-7">
          <Dialog.Close asChild>
            <button
              type="button"
              aria-label="Close"
              className="absolute right-4 top-4 inline-flex h-8 w-8 items-center justify-center rounded-lg text-cream-400 hover:bg-cream-100 hover:text-ink"
            >
              <X size={16} />
            </button>
          </Dialog.Close>

          <Dialog.Title className="font-display text-2xl font-bold text-ink">
            How the mapping works
          </Dialog.Title>

          <Dialog.Description className="mt-3 text-sm leading-relaxed text-cream-600">
            This website contains the functionality to browse the conda to PyPI
            mapping. As you might know a bunch of conda packages map to the same
            PyPI package. When installers like pixi need to create an
            environment with a mix of conda and PyPI packages, they use this
            mapping to resolve the overlap.
          </Dialog.Description>

          <SectionLabel>How it is built</SectionLabel>

          <p className="mt-2 text-sm leading-relaxed text-cream-600">
            The mapping is constructed by looking inside the packages. When a
            Python distribution is built into a conda package, that package
            still contains the project's Python metadata: the{" "}
            <Code>.dist-info</Code> folder pip/uv/pixi would usually install.
          </p>

          <ExtractionDiagram />

          <p className="mt-3 text-sm leading-relaxed text-cream-600">
            That folder is named for the PyPI distribution it came from, like{" "}
            <Code>numpy-1.26.4.dist-info</Code>. Parselmouth opens every conda
            package on a channel, reads that name, and records the conda to PyPI
            link. We do this hourly. And we create a number of different
            mappings for this.
          </p>

          <SectionLabel>Endpoints</SectionLabel>

          <p className="mt-2 text-sm leading-relaxed text-cream-600">
            The mapping is published as static files under{" "}
            <Code>conda-mapping.prefix.dev</Code>:
          </p>

          <ol className="mt-3 space-y-2.5 list-disc list-inside">
            <Endpoint
              path="hash-v0/{sha256}"
              desc="The PyPI mapping for a single conda artifact, keyed by its sha256."
            />
            <Endpoint
              path="hash-v0/{channel}/index.json"
              desc="Every conda artifact hash in a channel."
            />
            <Endpoint
              path="pypi-to-conda-v1/{channel}/{name}.json"
              desc="The conda packages and versions that provide a PyPI name."
            />
            <Endpoint
              path="relations-v1/{channel}/relations.jsonl.gz"
              desc="The full conda to PyPI relations table."
            />
          </ol>
          <SectionLabel>What does this Website actually show?</SectionLabel>

          <p className="mt-2 text-sm leading-relaxed text-cream-600">
            This website uses something called the{" "}
            <a
              className="text-blue-800"
              href="https://github.com/prefix-dev/parselmouth/blob/main/files/v0/conda-forge/compressed_mapping.json"
              target="_blank"
              rel="noopener noreferrer"
            >
              compressed mapping
            </a>
            , to built an index of all mapped conda packages. It then uses the
            index to browse the endpoints and retrieve the information from
            there. We then walk over the information and present it in a
            readable format.
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mt-6 font-display text-lg font-bold text-ink">{children}</h3>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-cream-100 px-1 py-px font-mono text-[12px] text-ink">
      {children}
    </code>
  );
}

function Endpoint({ path, desc }: { path: string; desc: string }) {
  return (
    <li>
      <code className="font-sans text-sm text-ink">{path}</code>
      <p className="mt-0.5 text-xs leading-snug text-cream-600">{desc}</p>
    </li>
  );
}

/**
 * Extraction-flow diagram: conda package, the .dist-info metadata inside it,
 * and the PyPI name parselmouth records.
 */
function ExtractionDiagram() {
  return (
    <div className="mt-6 overflow-x-auto">
      <svg
        viewBox="0 0 520 176"
        className="w-full min-w-[480px]"
        role="img"
        aria-label="A conda package contains Python dist-info metadata, from which the PyPI name is extracted."
      >
      {/* Stage 1: conda package */}
      <rect
        x="10"
        y="42"
        width="146"
        height="92"
        rx="12"
        className="fill-conda-bg-soft stroke-conda-border"
        strokeWidth="1.5"
      />
      <text
        x="83"
        y="82"
        textAnchor="middle"
        className="fill-conda-ink font-sans text-[8.5px] font-semibold uppercase"
        letterSpacing="0.1em"
      >
        conda package
      </text>
      <text
        x="83"
        y="104"
        textAnchor="middle"
        className="fill-ink font-mono text-[11px]"
      >
        numpy-1.26.4
      </text>

      {/* Arrow 1 */}
      <Arrow from={158} to={192} />

      {/* Stage 2: metadata inside */}
      <rect
        x="196"
        y="30"
        width="168"
        height="116"
        rx="12"
        className="fill-cream-50 stroke-rail"
        strokeWidth="1.5"
      />
      <text
        x="280"
        y="58"
        textAnchor="middle"
        className="fill-cream-500 font-sans text-[8.5px] font-semibold uppercase"
        letterSpacing="0.1em"
      >
        inside the package
      </text>
      <text x="216" y="86" className="fill-cream-400 font-mono text-[9px]">
        site-packages/
      </text>
      <rect
        x="212"
        y="97"
        width="146"
        height="20"
        rx="5"
        className="fill-conda-bg"
      />
      <text x="222" y="111" className="fill-conda-ink font-mono text-[9px]">
        numpy-1.26.4.dist-info/
      </text>
      <text x="226" y="133" className="fill-cream-400 font-mono text-[9px]">
        METADATA
      </text>

      {/* Arrow 2 */}
      <Arrow from={368} to={402} />

      {/* Stage 3: PyPI name */}
      <rect
        x="406"
        y="42"
        width="106"
        height="92"
        rx="12"
        className="fill-pypi-bg-soft stroke-pypi-border"
        strokeWidth="1.5"
      />
      <text
        x="459"
        y="82"
        textAnchor="middle"
        className="fill-pypi-ink font-sans text-[8.5px] font-semibold uppercase"
        letterSpacing="0.1em"
      >
        pypi distribution
      </text>
      <text
        x="459"
        y="104"
        textAnchor="middle"
        className="fill-ink font-mono text-[11px]"
      >
        numpy
      </text>
      </svg>
    </div>
  );
}

function Arrow({ from, to }: { from: number; to: number }) {
  const y = 88;
  return (
    <g className="stroke-cream-300">
      <line x1={from} y1={y} x2={to} y2={y} strokeWidth="1.5" />
      <path
        d={`M${to - 6} ${y - 4} L${to} ${y} L${to - 6} ${y + 4}`}
        fill="none"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </g>
  );
}
