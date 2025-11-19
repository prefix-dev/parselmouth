"""
Caching mechanism for channel indices.

This module implements HTTP-based caching for channel index files using
ETag and Last-Modified headers to avoid re-downloading large index files
when they haven't changed.
"""

import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import requests

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.http_utils import get_global_session
from parselmouth.internals.s3 import IndexMapping


logger = logging.getLogger(__name__)


def get_cache_dir() -> Path:
    """
    Get the cache directory for storing index files.

    Uses XDG_CACHE_HOME if set, otherwise falls back to ~/.cache
    """
    if cache_home := os.getenv("XDG_CACHE_HOME"):
        cache_dir = Path(cache_home) / "parselmouth"
    else:
        cache_dir = Path.home() / ".cache" / "parselmouth"

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_path(channel: SupportedChannels, base_url: str) -> tuple[Path, Path]:
    """
    Get paths for cache files.

    Args:
        channel: The conda channel
        base_url: Base URL for the endpoint

    Returns:
        Tuple of (index_file_path, metadata_file_path)
    """
    cache_dir = get_cache_dir()

    # Create a stable hash from the base URL
    url_hash = hashlib.md5(base_url.encode()).hexdigest()[:8]

    index_file = cache_dir / f"index_{channel}_{url_hash}.json"
    metadata_file = cache_dir / f"index_{channel}_{url_hash}.meta"

    return index_file, metadata_file


def load_cached_metadata(metadata_path: Path) -> dict[str, str]:
    """
    Load cache metadata (ETag, Last-Modified).

    Args:
        metadata_path: Path to metadata file

    Returns:
        Dict with 'etag' and 'last_modified' keys, empty if not found
    """
    if not metadata_path.exists():
        return {}

    try:
        with open(metadata_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load cache metadata: {e}")
        return {}


def save_cached_metadata(
    metadata_path: Path,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
):
    """
    Save cache metadata.

    Args:
        metadata_path: Path to metadata file
        etag: ETag header value
        last_modified: Last-Modified header value
    """
    metadata = {}
    if etag:
        metadata["etag"] = etag
    if last_modified:
        metadata["last_modified"] = last_modified

    try:
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)
    except OSError as e:
        logger.warning(f"Failed to save cache metadata: {e}")


def fetch_channel_index_cached(
    channel: SupportedChannels,
    base_url: str,
    timeout: int = 60,
    progress_callback: callable = None,
) -> tuple[Optional[IndexMapping], str]:
    """
    Fetch channel index with caching support.

    Uses HTTP conditional requests (If-None-Match, If-Modified-Since) to avoid
    re-downloading the index if it hasn't changed since last fetch.

    Args:
        channel: The conda channel
        base_url: Base URL for HTTP requests
        timeout: Request timeout in seconds
        progress_callback: Optional callback function(message: str) to report progress

    Returns:
        Tuple of (IndexMapping or None if fetch failed, status message for display)
    """
    session = get_global_session()
    url = f"{base_url.rstrip('/')}/hash-v0/{channel}/index.json"

    # Get cache paths
    index_path, metadata_path = get_cache_path(channel, base_url)

    # Load existing metadata
    cached_metadata = load_cached_metadata(metadata_path)

    # Prepare conditional request headers
    headers = {}
    if etag := cached_metadata.get("etag"):
        headers["If-None-Match"] = etag
    if last_modified := cached_metadata.get("last_modified"):
        headers["If-Modified-Since"] = last_modified

    try:
        # Report checking status
        if progress_callback:
            progress_callback("Checking for updates...")

        # Make request with conditional headers
        response = session.get(url, headers=headers, timeout=timeout)

        # 304 Not Modified - use cached version
        if response.status_code == 304:
            logger.info(f"✓ Index for {channel} not modified, using cache")
            if index_path.exists():
                try:
                    # Report loading from cache
                    if progress_callback:
                        progress_callback("Loading from cache...")

                    # Load JSON in a background thread to keep spinner alive
                    def load_json():
                        with open(index_path, "r") as f:
                            return json.load(f)

                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(load_json)

                        # Keep the spinner alive by periodically updating
                        while not future.done():
                            if progress_callback:
                                progress_callback("Parsing cached data...")
                            time.sleep(0.1)  # Small delay to let spinner update

                        data = future.result()

                    logger.info(f"✓ Loaded {len(data)} entries from cache")
                    return IndexMapping(root=data), "cached (up to date)"
                except (json.JSONDecodeError, OSError) as e:
                    logger.error(f"Failed to load cached index: {e}")
                    # Fall through to re-download
            else:
                logger.warning("Got 304 but cache file missing, re-downloading")

        # 404 Not Found
        if response.status_code == 404:
            logger.warning(f"Channel index not found at {url}")
            return None, "not found"

        # Raise for other errors
        response.raise_for_status()

        # 200 OK - parse and cache new data
        size_mb = len(response.content) / (1024 * 1024)
        logger.info(f"Downloaded fresh index for {channel} ({size_mb:.2f} MB)")

        # Report downloading
        if progress_callback:
            progress_callback(f"Downloading index ({size_mb:.1f} MB)...")

        data = response.json()

        # Report parsing
        if progress_callback:
            progress_callback("Parsing index...")

        # Save to cache
        try:
            # Remove old cache file if it exists (to avoid stale data)
            if index_path.exists():
                logger.info(f"Removing old cache file: {index_path.name}")
                index_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()

            # Write new cache
            if progress_callback:
                progress_callback("Saving to cache...")

            with open(index_path, "w") as f:
                json.dump(data, f)

            # Save metadata
            save_cached_metadata(
                metadata_path,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
            logger.info(f"Cached index for {channel}")
        except OSError as e:
            logger.warning(f"Failed to cache index: {e}")

        return IndexMapping(root=data), f"downloaded ({size_mb:.1f} MB)"

    except requests.RequestException as exc:
        logger.error(f"Failed to fetch channel index from {url}: {exc}")

        # Try to use stale cache as fallback
        if index_path.exists():
            logger.info(f"Using stale cache for {channel} as fallback")
            if progress_callback:
                progress_callback("Loading stale cache (network error)...")

            try:
                # Load JSON in background thread to keep spinner alive
                def load_json():
                    with open(index_path, "r") as f:
                        return json.load(f)

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(load_json)

                    # Keep the spinner alive
                    while not future.done():
                        if progress_callback:
                            progress_callback("Parsing stale cache...")
                        time.sleep(0.1)

                    data = future.result()

                return IndexMapping(root=data), "cached (stale, network error)"
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to load cached index: {e}")

        return None, "failed"


def clear_cache(channel: Optional[SupportedChannels] = None):
    """
    Clear cached index files.

    Args:
        channel: If specified, only clear cache for this channel.
                 If None, clear all caches.
    """
    cache_dir = get_cache_dir()

    if channel:
        # Clear specific channel
        pattern = f"index_{channel}_*.json"
    else:
        # Clear all
        pattern = "index_*.json"

    removed_count = 0
    for file_path in cache_dir.glob(pattern):
        try:
            file_path.unlink()
            # Also remove metadata file
            meta_path = file_path.with_suffix(".meta")
            if meta_path.exists():
                meta_path.unlink()
            removed_count += 1
        except OSError as e:
            logger.warning(f"Failed to remove cache file {file_path}: {e}")

    logger.info(f"Removed {removed_count} cached index file(s)")
    return removed_count


def get_cache_info() -> dict[str, dict]:
    """
    Get information about cached index files.

    Returns:
        Dict mapping cache file names to their info (size, mtime, etc.)
    """
    cache_dir = get_cache_dir()
    info = {}

    for file_path in cache_dir.glob("index_*.json"):
        try:
            stat = file_path.stat()
            meta_path = file_path.with_suffix(".meta")
            metadata = load_cached_metadata(meta_path) if meta_path.exists() else {}

            info[file_path.name] = {
                "size_bytes": stat.st_size,
                "size_mb": stat.st_size / (1024 * 1024),
                "modified_time": stat.st_mtime,
                "etag": metadata.get("etag"),
                "last_modified": metadata.get("last_modified"),
            }
        except OSError as e:
            logger.warning(f"Failed to stat {file_path}: {e}")

    return info
