import Fuse from "fuse.js";
import { useMemo } from "react";
import { useCompressedMapping, type Channel, type CompressedMapping } from "./api";

export type Side = "conda" | "pypi";

export interface SearchHit {
  side: Side;
  name: string;
}

export interface DerivedIndex {
  /** Conda → list of PyPI names (nulls dropped). */
  pairs: Record<string, string[]>;
  /** Reverse lookup: PyPI name → conda packages that ship it. */
  reverse: Record<string, string[]>;
  /** Fast existence checks. */
  hasConda: Set<string>;
  hasPypi: Set<string>;
  condaCount: number;
  pypiCount: number;
}

export interface NameSearcher extends DerivedIndex {
  search(query: string, limit?: number): SearchHit[];
}

interface FuseEntry {
  side: Side;
  name: string;
}

const FUSE_OPTIONS: ConstructorParameters<typeof Fuse<FuseEntry>>[1] = {
  keys: ["name"],
  threshold: 0.3,
  ignoreLocation: true,
  minMatchCharLength: 2,
  includeScore: true,
};

/**
 * Build the derived indices from the raw compressed mapping.
 * Cheap (~30 ms for conda-forge's 32k entries) — runs in a useMemo.
 */
export function deriveIndex(mapping: CompressedMapping): DerivedIndex {
  // Prototype-less so package names like "constructor", "toString",
  // "hasOwnProperty" don't collide with Object.prototype keys.
  const pairs = Object.create(null) as Record<string, string[]>;
  const reverse = Object.create(null) as Record<string, string[]>;
  const pypiSet = new Set<string>();

  for (const [condaName, pypis] of Object.entries(mapping)) {
    if (!pypis || pypis.length === 0) continue;
    pairs[condaName] = pypis;
    for (const p of pypis) {
      pypiSet.add(p);
      const bucket = reverse[p];
      if (bucket) {
        bucket.push(condaName);
      } else {
        reverse[p] = [condaName];
      }
    }
  }

  return {
    pairs,
    reverse,
    hasConda: new Set(Object.keys(mapping)),
    hasPypi: pypiSet,
    condaCount: Object.keys(mapping).length,
    pypiCount: pypiSet.size,
  };
}

/**
 * Hook: fetch compressed mapping (cached by TanStack Query across consumers)
 * and derive the index. Cheap re-derivation is fine; only one fetch happens
 * per channel.
 */
export function useDerivedIndex(channel: Channel) {
  const query = useCompressedMapping(channel);
  const index = useMemo(
    () => (query.data ? deriveIndex(query.data) : null),
    [query.data],
  );
  return { ...query, index };
}

/**
 * Hook: same fetch as useDerivedIndex, plus a Fuse fuzzy-search index on top.
 * The Fuse construction is only paid by consumers that need search.
 */
export function useNameSearcher(channel: Channel): NameSearcher | null {
  const { data, index } = useDerivedIndex(channel);
  return useMemo(() => {
    if (!data || !index) return null;
    const entries: FuseEntry[] = [
      ...Array.from(index.hasConda).map((name) => ({
        side: "conda" as const,
        name,
      })),
      ...Array.from(index.hasPypi).map((name) => ({
        side: "pypi" as const,
        name,
      })),
    ];
    const fuse = new Fuse(entries, FUSE_OPTIONS);

    return {
      ...index,
      search(query, limit = 20) {
        const trimmed = query.trim();
        if (!trimmed) return [];

        // Exact-match first so they lead the dropdown.
        const exact: SearchHit[] = [];
        if (index.hasConda.has(trimmed))
          exact.push({ side: "conda", name: trimmed });
        if (index.hasPypi.has(trimmed))
          exact.push({ side: "pypi", name: trimmed });

        const fuzzy = fuse
          .search(trimmed, { limit: limit + exact.length })
          .map((r) => ({ side: r.item.side, name: r.item.name }))
          .filter((h) => h.name !== trimmed);

        return [...exact, ...fuzzy].slice(0, limit);
      },
    };
  }, [data, index]);
}

// Re-export so consumers can keep `import { type Channel } from "./names"` if convenient.
export type { CompressedMapping };

export function lookupCondaToPypi(
  index: DerivedIndex | null | undefined,
  condaName: string,
): string[] | null {
  if (!index) return null;
  return index.pairs[condaName] ?? null;
}

export function lookupPypiToConda(
  index: DerivedIndex | null | undefined,
  pypiName: string,
): string[] {
  if (!index) return [];
  return index.reverse[pypiName] ?? [];
}
