import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "./utils";
import { normalizePypi } from "./pypi";

export type Channel = "conda-forge" | "bioconda";

export const CHANNELS: { value: Channel; label: string }[] = [
  { value: "conda-forge", label: "conda-forge" },
  { value: "bioconda", label: "bioconda" },
];

/**
 * Raw conda → pypi name mapping shipped from the parselmouth repo at
 * files/v0/{channel}/compressed_mapping.json. Conda names that have no
 * known PyPI counterpart map to `null`. ~925 KB raw / ~190 KB gzipped
 * for conda-forge.
 *
 * The frontend derives both the autocomplete name index and the
 * conda→pypi pairs index from this single source in memory.
 */
export type CompressedMapping = Record<string, string[] | null>;

/**
 * pypi-to-conda-v1 file shape on R2. The live format has `conda_versions`
 * values as a single conda-name string; older docs show arrays for
 * vendoring cases — we accept both.
 */
export interface PypiToCondaDetail {
  format_version?: string;
  channel?: string;
  pypi_name: string;
  conda_versions: Record<string, string | string[]>;
}

export function condaNamesFor(value: string | string[]): string[] {
  return Array.isArray(value) ? value : [value];
}

// raw.githubusercontent.com sends CORS headers, so production fetches go direct.
// In dev we proxy through /api/gh to keep things same-origin and quiet.
const GH_BASE = import.meta.env.DEV
  ? "/api/gh"
  : "https://raw.githubusercontent.com";

const REPO_PATH = "prefix-dev/parselmouth/main/files/v0";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} – ${url}`);
  }
  return (await res.json()) as T;
}

export function useCompressedMapping(channel: Channel) {
  return useQuery({
    queryKey: ["compressed-mapping", channel],
    queryFn: () =>
      fetchJson<CompressedMapping>(
        `${GH_BASE}/${REPO_PATH}/${channel}/compressed_mapping.json`,
      ),
  });
}

export function usePypiDetail(channel: Channel, pypiName: string | null) {
  return useQuery({
    enabled: !!pypiName,
    queryKey: ["pypi-detail", channel, pypiName],
    queryFn: () => {
      const normalized = normalizePypi(pypiName!);
      return fetchJson<PypiToCondaDetail>(
        `${API_BASE}/pypi-to-conda-v1/${channel}/${normalized}.json`,
      );
    },
  });
}
