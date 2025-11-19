"""
HTTP helper utilities for accessing the public bucket endpoints (hash + PyPI lookups).

All helpers in this module use plain HTTP(S) so they work for both production
(`https://conda-mapping.prefix.dev`) and locally hosted MinIO buckets
(`http://localhost:9000/conda`).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from packaging.utils import canonicalize_name
import requests

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.http_utils import get_global_session
from parselmouth.internals.package_relations import PyPIPackageLookup
from parselmouth.internals.s3 import IndexMapping, MappingEntry

logger = logging.getLogger(__name__)

# Default base URL hosts the production bucket. Users can override it with
# CONDA_MAPPING_BASE_URL to point at a local MinIO deployment.
DEFAULT_MAPPING_BASE_URL = "https://conda-mapping.prefix.dev"


def _resolve_base_url(override: str | None = None) -> str:
    """Resolve the base URL, honoring an override or environment variable."""
    if override:
        return override.rstrip("/")
    env_base = os.getenv("CONDA_MAPPING_BASE_URL")
    if env_base:
        return env_base.rstrip("/")
    return DEFAULT_MAPPING_BASE_URL


def _build_url(base_url: str, *parts: str) -> str:
    """Join path parts with the base URL."""
    cleaned_parts = [part.strip("/") for part in parts if part]
    if not cleaned_parts:
        return base_url
    return "/".join([base_url.rstrip("/"), *cleaned_parts])


def fetch_channel_index_http(
    channel: SupportedChannels,
    *,
    base_url: str | None = None,
    timeout: int = 60,
) -> IndexMapping | None:
    """
    Download the channel index (`hash-v0/{channel}/index.json`) via HTTP.

    Returns None if the index is missing or the request fails.
    """
    resolved_base = _resolve_base_url(base_url)
    url = _build_url(resolved_base, "hash-v0", str(channel), "index.json")
    session = get_global_session()

    try:
        response = session.get(url, timeout=timeout)
        if response.status_code == 404:
            logger.warning("Channel index not found at %s", url)
            return None
        response.raise_for_status()
        return IndexMapping(root=response.json())
    except requests.RequestException as exc:
        logger.error("Failed to download channel index from %s: %s", url, exc)
        return None


def fetch_mapping_entry_by_hash(
    package_hash: str,
    *,
    base_url: str | None = None,
    timeout: int = 30,
) -> MappingEntry | None:
    """
    Fetch a single hash mapping entry (`hash-v0/{sha256}`) via HTTP.

    Args:
        package_hash: The SHA256 hash from repodata.
        base_url: Optional override for the bucket root.
        timeout: Request timeout in seconds.
    """
    resolved_base = _resolve_base_url(base_url)
    url = _build_url(resolved_base, "hash-v0", package_hash)
    session = get_global_session()

    try:
        response = session.get(url, timeout=timeout)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return MappingEntry.model_validate(response.json())
    except (requests.RequestException, ValueError) as exc:
        logger.error("Failed to fetch mapping for %s from %s: %s", package_hash, url, exc)
        return None


def _build_v1_lookup_payload(data: dict[str, Any]) -> PyPIPackageLookup | None:
    """Validate v1 lookup payloads."""
    try:
        return PyPIPackageLookup.model_validate(data)
    except ValueError as exc:
        logger.error("Invalid PyPI lookup payload: %s", exc)
    return None


def fetch_pypi_lookup(
    channel: SupportedChannels,
    pypi_name: str,
    *,
    base_url: str | None = None,
    timeout: int = 30,
) -> PyPIPackageLookup | None:
    """
    Fetch the PyPI -> Conda lookup JSON.

    Tries the v1 endpoint first (`pypi-to-conda-v1/{channel}/{name}.json`),
    and falls back to the legacy v0 endpoint if v1 is unavailable.
    """
    resolved_base = _resolve_base_url(base_url)
    normalized = canonicalize_name(pypi_name)
    session = get_global_session()

    # Preferred v1 format
    v1_url = _build_url(
        resolved_base,
        "pypi-to-conda-v1",
        str(channel),
        f"{normalized}.json",
    )
    try:
        v1_response = session.get(v1_url, timeout=timeout)
        if v1_response.status_code == 200:
            return _build_v1_lookup_payload(v1_response.json())
    except requests.RequestException as exc:
        logger.debug("PyPI lookup v1 request failed for %s: %s", normalized, exc)

    # Legacy v0 fallback (plain mapping dict)
    v0_url = _build_url(
        resolved_base,
        "pypi-to-conda-v0",
        str(channel),
        f"{normalized}.json",
    )
    try:
        v0_response = session.get(v0_url, timeout=timeout)
        if v0_response.status_code == 404:
            return None
        v0_response.raise_for_status()
        conda_versions = v0_response.json()
        if not isinstance(conda_versions, dict):
            logger.error("Unexpected PyPI lookup shape at %s", v0_url)
            return None
        return PyPIPackageLookup(
            channel=str(channel),
            pypi_name=normalized,
            conda_versions=conda_versions,  # type: ignore[arg-type]
        )
    except (requests.RequestException, ValueError) as exc:
        logger.error("PyPI lookup request failed for %s: %s", normalized, exc)
        return None

