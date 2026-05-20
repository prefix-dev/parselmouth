import { useCallback, useEffect, useMemo, useState } from "react";
import { type Channel, type CompressedMapping } from "./api";

export interface PixiMappingCartItem {
  channel: Channel;
  condaName: string;
  addedAt: number;
}

export type PixiMappingJson = Record<string, string | null>;

const STORAGE_PREFIX = "parselmouth:pixi-mapping-cart:v1";

export function pixiMappingCartStorageKey(channel: Channel) {
  return `${STORAGE_PREFIX}:${channel}`;
}

function readCart(channel: Channel): PixiMappingCartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(pixiMappingCartStorageKey(channel));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(isCartItem)
      .filter((item) => item.channel === channel)
      .sort((a, b) => a.addedAt - b.addedAt);
  } catch {
    return [];
  }
}

function isCartItem(value: unknown): value is PixiMappingCartItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<PixiMappingCartItem>;
  return (
    (item.channel === "conda-forge" || item.channel === "bioconda") &&
    typeof item.condaName === "string" &&
    typeof item.addedAt === "number"
  );
}

function writeCart(channel: Channel, items: PixiMappingCartItem[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    pixiMappingCartStorageKey(channel),
    JSON.stringify(items),
  );
}

export function usePixiMappingCart(channel: Channel) {
  const [items, setItems] = useState<PixiMappingCartItem[]>(() =>
    readCart(channel),
  );

  useEffect(() => {
    setItems(readCart(channel));
  }, [channel]);

  useEffect(() => {
    // When `channel` changes, React first renders with the previous channel's
    // items before the read effect above replaces them. Avoid writing those
    // stale items into the new channel's localStorage slot.
    if (items.some((item) => item.channel !== channel)) return;
    writeCart(channel, items);
  }, [channel, items]);

  const names = useMemo(() => new Set(items.map((item) => item.condaName)), [items]);

  const add = useCallback(
    (condaName: string) => {
      setItems((current) => {
        if (current.some((item) => item.condaName === condaName)) return current;
        return [...current, { channel, condaName, addedAt: Date.now() }];
      });
    },
    [channel],
  );

  const remove = useCallback((condaName: string) => {
    setItems((current) =>
      current.filter((item) => item.condaName !== condaName),
    );
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const has = useCallback(
    (condaName: string) => names.has(condaName),
    [names],
  );

  return { items, names, add, remove, clear, has };
}

export function buildPixiMappingJson(
  items: PixiMappingCartItem[],
  mapping: CompressedMapping,
): PixiMappingJson {
  const output: PixiMappingJson = {};
  const sorted = [...items].sort((a, b) => a.condaName.localeCompare(b.condaName));
  for (const item of sorted) {
    const pypiNames = mapping[item.condaName];
    const closest = closestMappedName(item.condaName, pypiNames);
    if (closest) output[item.condaName] = closest;
  }
  return output;
}

export function closestMappedName(
  condaName: string,
  pypiNames: string[] | null | undefined,
): string | null {
  if (!pypiNames?.length) return null;
  let best = pypiNames[0];
  let bestDistance = editDistance(condaName, best);
  for (const candidate of pypiNames.slice(1)) {
    const distance = editDistance(condaName, candidate);
    if (distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }
  return best;
}

function editDistance(a: string, b: string): number {
  const left = a.toLowerCase();
  const right = b.toLowerCase();
  const previous = Array.from({ length: right.length + 1 }, (_, i) => i);
  const current = Array<number>(right.length + 1);

  for (let i = 1; i <= left.length; i++) {
    current[0] = i;
    for (let j = 1; j <= right.length; j++) {
      const cost = left[i - 1] === right[j - 1] ? 0 : 1;
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + cost,
      );
    }
    previous.splice(0, previous.length, ...current);
  }

  return previous[right.length];
}

export function pixiMappingFilename(channel: Channel) {
  return `pixi-conda-pypi-map-${channel}.json`;
}

export function downloadPixiMapping(
  channel: Channel,
  mapping: PixiMappingJson,
) {
  const blob = new Blob([`${JSON.stringify(mapping, null, 2)}\n`], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = pixiMappingFilename(channel);
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
