import type { Channel } from "./api";
import { normalizePypi } from "./pypi";

/**
 * Canonical conda package page on prefix.dev.
 * https://prefix.dev/channels/{channel}/packages/{name}
 */
export function condaPackageUrl(channel: Channel, condaName: string): string {
  return `https://prefix.dev/channels/${channel}/packages/${encodeURIComponent(
    condaName,
  )}`;
}

/**
 * PyPI project page. PyPI accepts both normalized and unnormalized names
 * (it redirects), but linking with the PEP 503 normalized form skips that hop.
 */
export function pypiPackageUrl(pypiName: string): string {
  return `https://pypi.org/project/${encodeURIComponent(
    normalizePypi(pypiName),
  )}/`;
}

/**
 * PyPI project page at a specific release.
 * https://pypi.org/project/{name}/{version}/
 */
export function pypiVersionUrl(pypiName: string, version: string): string {
  return `https://pypi.org/project/${encodeURIComponent(
    normalizePypi(pypiName),
  )}/${encodeURIComponent(version)}/`;
}
