"""Data structures for organizing channel indices by package and version."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from parselmouth.internals.channels import SupportedChannels
from .index_cache import get_cache_dir
from parselmouth.internals.s3 import IndexMapping, MappingEntry

from .common import console, logger

PackageVersions = dict[str, list[tuple[str, MappingEntry]]]


@dataclass
class PackageCatalog:
    """Organizes packages by name and version."""

    packages_by_name: dict[str, PackageVersions]

    @classmethod
    def from_index(
        cls, index: IndexMapping, show_progress: bool = True
    ) -> "PackageCatalog":
        packages = cls._build_packages(index, show_progress)
        return cls(packages_by_name=packages)

    @classmethod
    def from_index_cached(
        cls,
        index: IndexMapping,
        channel: SupportedChannels,
        base_url: str,
        cache_status: str | None,
        show_progress: bool = True,
    ) -> "PackageCatalog":
        cache_path = _catalog_cache_path(channel, base_url)
        can_use_cache = cache_status and cache_status.startswith("cached")

        if can_use_cache and cache_path.exists():
            serialized = _load_catalog_cache(cache_path)
            if serialized is not None:
                packages = cls._deserialize(serialized, index)
                if packages is not None:
                    logger.info("Loaded package catalog from cache")
                    return cls(packages_by_name=packages)
                logger.debug("Package catalog cache invalid due to missing entries")

        packages = cls._build_packages(index, show_progress)
        _save_catalog_cache(cache_path, cls._serialize(packages))
        return cls(packages_by_name=packages)

    @staticmethod
    def _build_packages(
        index: IndexMapping, show_progress: bool
    ) -> dict[str, PackageVersions]:
        packages_by_name: dict[str, PackageVersions] = {}

        def add_entry(pkg_hash: str, entry: MappingEntry):
            conda_name = entry.conda_name
            pkg_filename = entry.package_name
            pkg_base = pkg_filename.replace(".tar.bz2", "").replace(".conda", "")
            parts = pkg_base.rsplit("-", 2)
            pkg_version = parts[1] if len(parts) >= 2 else "unknown"

            if conda_name not in packages_by_name:
                packages_by_name[conda_name] = {}
            if pkg_version not in packages_by_name[conda_name]:
                packages_by_name[conda_name][pkg_version] = []

            packages_by_name[conda_name][pkg_version].append((pkg_hash, entry))

        if show_progress:
            total = len(index.root)
            with Progress(
                SpinnerColumn(),
                BarColumn(bar_width=40),
                TaskProgressColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Preparing catalog", total=total)
                for idx, (pkg_hash, entry) in enumerate(index.root.items(), 1):
                    add_entry(pkg_hash, entry)
                    progress.update(
                        task,
                        advance=1,
                        description=f"[green]Processed {idx}/{total} entries",
                    )
        else:
            for pkg_hash, entry in index.root.items():
                add_entry(pkg_hash, entry)

        return packages_by_name

    @staticmethod
    def _serialize(
        packages_by_name: dict[str, PackageVersions],
    ) -> dict[str, dict[str, list[str]]]:
        return {
            name: {
                version: [pkg_hash for pkg_hash, _ in builds]
                for version, builds in versions.items()
            }
            for name, versions in packages_by_name.items()
        }

    @staticmethod
    def _deserialize(
        serialized: dict[str, dict[str, list[str]]],
        index: IndexMapping,
    ) -> dict[str, PackageVersions] | None:
        packages_by_name: dict[str, PackageVersions] = {}

        for name, versions in serialized.items():
            packages_by_name[name] = {}
            for version, hashes in versions.items():
                builds: list[tuple[str, MappingEntry]] = []
                for pkg_hash in hashes:
                    entry = index.root.get(pkg_hash)
                    if entry is None:
                        return None
                    builds.append((pkg_hash, entry))
                packages_by_name[name][version] = builds

        return packages_by_name

    def search(self, query: str) -> dict[str, PackageVersions]:
        if query in self.packages_by_name:
            return {query: self.packages_by_name[query]}

        lowered = query.lower()
        return {
            name: versions
            for name, versions in self.packages_by_name.items()
            if lowered in name.lower()
        }

    def suggestions(self, limit: int = 20) -> list[str]:
        return sorted(self.packages_by_name.keys())[:limit]


def _catalog_cache_path(channel: SupportedChannels, base_url: str):
    cache_dir = get_cache_dir()
    url_hash = hashlib.md5(base_url.encode()).hexdigest()[:8]
    return cache_dir / f"catalog_{channel}_{url_hash}.json"


def _load_catalog_cache(cache_path):
    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Failed to load package catalog cache: {exc}")
        return None


def _save_catalog_cache(cache_path, payload: dict):
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(payload, f)
    except OSError as exc:
        logger.warning(f"Failed to write package catalog cache: {exc}")


__all__ = ["PackageCatalog", "PackageVersions"]
