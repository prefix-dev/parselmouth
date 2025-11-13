"""
Package Relations Table - Single Source of Truth

This module implements a table-based approach for storing the relationship between
Conda packages and PyPI packages. The relationship "conda package C includes PyPI
package P at version V" is stored as rows in a table.

From this master table, we can efficiently generate:
- PyPI -> Conda lookups
- Conda (hash) -> PyPI lookups
- Analytics and statistics

The table is stored as JSON Lines (.jsonl) format for:
- Streaming support (can read/write incrementally)
- Human readability (one JSON object per line)
- Easy appending (just add new lines)
- Simple processing (no complex parsing)
"""

import gzip
import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field, field_validator

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping, MappingEntry
from parselmouth.internals.types import (
    CondaFileName,
    CondaPackageName,
    CondaVersion,
    PyPIName,
    PyPISourceUrl,
    PyPIVersion,
)

logger = logging.getLogger(__name__)


def parse_conda_filename(filename: CondaFileName) -> tuple[CondaVersion, str]:
    """
    Parse conda filename to extract version and build string.

    Example: "numpy-1.26.4-py311h64a7726_0.conda" -> ("1.26.4", "py311h64a7726_0")

    Args:
        filename: Conda package filename

    Returns:
        Tuple of (version, build_string)
    """
    # Remove .conda or .tar.bz2 extension
    name = filename.replace('.conda', '').replace('.tar.bz2', '')

    # Split by '-' to get [package_name, version, build]
    # Note: package name itself might contain '-', so we split from the right
    parts = name.rsplit('-', 2)

    if len(parts) >= 3:
        version = parts[-2]
        build = parts[-1]
        return version, build

    # Fallback if parsing fails
    logger.warning(f"Could not parse conda filename: {filename}")
    return "unknown", "unknown"


class CondaPackageVersion(BaseModel):
    """
    Information about a conda package version that provides a PyPI package.

    This includes the conda package name, version, and all build variants.
    """

    name: CondaPackageName
    version: CondaVersion
    builds: list[str] = Field(
        description="List of build strings for this version (e.g., ['py311h64a7726_0', 'py310h4bfa8fc_0'])"
    )


class PackageRelation(BaseModel):
    """
    A single relation representing that a conda package includes a PyPI package.

    This is the atomic unit of the mapping. Multiple relations form the complete
    mapping table.
    """

    # Conda package information
    conda_name: CondaPackageName
    conda_filename: CondaFileName
    conda_hash: str = Field(description="SHA256 hash of the conda package")

    # PyPI package information
    pypi_name: PyPIName
    pypi_version: PyPIVersion

    # Metadata
    channel: str
    direct_url: Optional[list[PyPISourceUrl]] = Field(
        default=None,
        description="Direct URLs when package is not on PyPI index"
    )

    @field_validator('conda_hash')
    @classmethod
    def validate_hash(cls, v: str) -> str:
        """Ensure hash is lowercase hex string"""
        if not all(c in '0123456789abcdef' for c in v):
            raise ValueError(f"Hash must be lowercase hex string, got: {v}")
        return v


class RelationsTableMetadata(BaseModel):
    """Metadata for the relations table"""

    format_version: str = Field(default="1.0", description="Table format version")
    channel: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_relations: int
    unique_conda_packages: int
    unique_pypi_packages: int
    description: str = "Conda to PyPI package relations table"


class RelationsTable:
    """
    Manages the package relations table.

    The table is stored as JSON Lines format where each line is a PackageRelation.
    This allows for streaming reads/writes and easy appending.
    """

    def __init__(self, channel: SupportedChannels):
        self.channel = channel
        self.relations: list[PackageRelation] = []

    @classmethod
    def from_conda_to_pypi_index(
        cls,
        index: IndexMapping,
        channel: SupportedChannels
    ) -> "RelationsTable":
        """
        Build relations table from existing conda->pypi hash-based index.

        This converts the existing mapping structure into a normalized table.
        """
        table = cls(channel)

        logger.info(f"Building relations table from {len(index.root)} conda packages")

        for conda_hash, entry in index.root.items():
            relations = cls._entry_to_relations(conda_hash, entry, str(channel))
            table.relations.extend(relations)

        logger.info(f"Created table with {len(table.relations)} relations")
        return table

    @staticmethod
    def _entry_to_relations(
        conda_hash: str,
        entry: MappingEntry,
        channel: str
    ) -> list[PackageRelation]:
        """Convert a MappingEntry to one or more PackageRelation objects"""
        relations = []

        if not entry.pypi_normalized_names:
            return relations

        # Each conda package can map to multiple PyPI packages
        for pypi_name in entry.pypi_normalized_names:
            if not entry.versions or pypi_name not in entry.versions:
                logger.warning(
                    f"No version found for {pypi_name} in {entry.package_name}"
                )
                continue

            relation = PackageRelation(
                conda_name=entry.conda_name,
                conda_filename=entry.package_name,
                conda_hash=conda_hash,
                pypi_name=pypi_name,
                pypi_version=entry.versions[pypi_name],
                channel=channel,
                direct_url=entry.direct_url,
            )
            relations.append(relation)

        return relations

    def to_jsonl(self, compress: bool = True) -> bytes:
        """
        Serialize table to JSON Lines format.

        Args:
            compress: If True, gzip compress the output

        Returns:
            Bytes containing the JSONL data (optionally compressed)
        """
        lines = []
        for relation in self.relations:
            lines.append(relation.model_dump_json())

        jsonl_content = "\n".join(lines).encode("utf-8")

        if compress:
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode='wb') as gz:
                gz.write(jsonl_content)
            return buffer.getvalue()

        return jsonl_content

    @classmethod
    def from_jsonl(cls, data: bytes, channel: SupportedChannels, compressed: bool = True) -> "RelationsTable":
        """
        Load table from JSON Lines format.

        Args:
            data: The JSONL data as bytes
            channel: The channel this table belongs to
            compressed: If True, decompress with gzip first

        Returns:
            RelationsTable instance
        """
        table = cls(channel)

        if compressed:
            data = gzip.decompress(data)

        for line in data.decode("utf-8").splitlines():
            if line.strip():
                relation = PackageRelation.model_validate_json(line)
                table.relations.append(relation)

        return table

    def iter_relations(self) -> Iterator[PackageRelation]:
        """Iterate over all relations"""
        return iter(self.relations)

    def get_metadata(self) -> RelationsTableMetadata:
        """Generate metadata about the table"""
        unique_conda = set((r.conda_name, r.conda_hash) for r in self.relations)
        unique_pypi = set(r.pypi_name for r in self.relations)

        return RelationsTableMetadata(
            channel=str(self.channel),
            total_relations=len(self.relations),
            unique_conda_packages=len(unique_conda),
            unique_pypi_packages=len(unique_pypi),
        )

    def generate_pypi_to_conda_lookups(self) -> dict[PyPIName, dict[PyPIVersion, list[CondaPackageVersion]]]:
        """
        Generate PyPI -> Conda lookup mapping from the table.

        Returns dict of: {pypi_name: {pypi_version: [CondaPackageVersion]}}

        This is a derived view - the table is the source of truth.
        """
        logger.info("Generating PyPI -> Conda lookups from relations table")

        # Build intermediate structure: {pypi_name: {pypi_version: {conda_name: {conda_version: [builds]}}}}
        lookup: dict[PyPIName, dict[PyPIVersion, dict[CondaPackageName, dict[CondaVersion, set[str]]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        )

        for relation in self.relations:
            # Parse conda filename to get version and build
            conda_version, build_string = parse_conda_filename(relation.conda_filename)

            # Add to nested structure
            lookup[relation.pypi_name][relation.pypi_version][relation.conda_name][conda_version].add(build_string)

        # Convert to final structure with CondaPackageVersion objects
        result: dict[PyPIName, dict[PyPIVersion, list[CondaPackageVersion]]] = {}
        for pypi_name, versions in lookup.items():
            result[pypi_name] = {}
            for pypi_version, conda_packages in versions.items():
                conda_pkg_versions = []
                for conda_name, conda_versions in sorted(conda_packages.items()):
                    for conda_version, builds in sorted(conda_versions.items()):
                        conda_pkg_versions.append(
                            CondaPackageVersion(
                                name=conda_name,
                                version=conda_version,
                                builds=sorted(builds)
                            )
                        )
                result[pypi_name][pypi_version] = conda_pkg_versions

        logger.info(f"Generated lookups for {len(result)} PyPI packages")
        return result

    def generate_conda_to_pypi_lookups(self) -> dict[str, MappingEntry]:
        """
        Generate Conda (hash) -> PyPI lookup mapping from the table.

        Returns dict of: {conda_hash: MappingEntry}

        This reconstructs the original MappingEntry format from the table.
        """
        logger.info("Generating Conda -> PyPI lookups from relations table")

        # Group relations by conda hash
        by_hash: dict[str, list[PackageRelation]] = defaultdict(list)
        for relation in self.relations:
            by_hash[relation.conda_hash].append(relation)

        result = {}
        for conda_hash, relations in by_hash.items():
            # All relations for same hash should have same conda info
            first = relations[0]

            pypi_names = [r.pypi_name for r in relations]
            versions = {r.pypi_name: r.pypi_version for r in relations}

            # Take direct_url from first relation (should be same for all)
            direct_url = first.direct_url

            entry = MappingEntry(
                pypi_normalized_names=pypi_names,
                versions=versions,
                conda_name=first.conda_name,
                package_name=first.conda_filename,
                direct_url=direct_url,
            )
            result[conda_hash] = entry

        logger.info(f"Generated lookups for {len(result)} Conda packages")
        return result


class PyPIPackageLookupDetailed(BaseModel):
    """
    Detailed lookup response for a single PyPI package.

    This includes full version and build information for conda packages.
    This is what gets served at: /pypi-to-conda-v1/{channel}/{pypi_name}-detailed.json
    """

    format_version: str = "1.0"
    channel: str
    pypi_name: PyPIName
    conda_versions: dict[PyPIVersion, list[CondaPackageVersion]] = Field(
        description="Map of PyPI version to list of Conda packages (with versions and builds) that provide it"
    )

    def to_json_bytes(self) -> bytes:
        """Serialize to JSON bytes for uploading"""
        return self.model_dump_json(indent=None).encode("utf-8")


class PyPIPackageLookup(BaseModel):
    """
    Simplified lookup response for a single PyPI package.

    This only includes conda package names, without version/build details.
    This is what gets served at: /pypi-to-conda-v1/{channel}/{pypi_name}.json
    """

    format_version: str = "1.0"
    channel: str
    pypi_name: PyPIName
    conda_versions: dict[PyPIVersion, list[CondaPackageName]] = Field(
        description="Map of PyPI version to list of Conda package names that provide it"
    )

    def to_json_bytes(self) -> bytes:
        """Serialize to JSON bytes for uploading"""
        return self.model_dump_json(indent=None).encode("utf-8")


def create_pypi_lookup_files_detailed(
    table: RelationsTable,
) -> dict[PyPIName, PyPIPackageLookupDetailed]:
    """
    Create detailed individual lookup files for each PyPI package.

    These include full version and build information for conda packages.
    These are the files that will be served at:
    /pypi-to-conda-v1/{channel}/{pypi_name}-detailed.json

    Returns:
        Dict mapping pypi_name to its detailed lookup object
    """
    pypi_to_conda = table.generate_pypi_to_conda_lookups()

    lookups = {}
    for pypi_name, versions in pypi_to_conda.items():
        lookup = PyPIPackageLookupDetailed(
            channel=str(table.channel),
            pypi_name=pypi_name,
            conda_versions=versions,
        )
        lookups[pypi_name] = lookup

    return lookups


def create_pypi_lookup_files(
    table: RelationsTable,
) -> dict[PyPIName, PyPIPackageLookup]:
    """
    Create simplified individual lookup files for each PyPI package.

    This version only includes conda package names (not versions/builds).
    These are the files that will be served at:
    /pypi-to-conda-v1/{channel}/{pypi_name}.json

    Returns:
        Dict mapping pypi_name to its simplified lookup object
    """
    pypi_to_conda = table.generate_pypi_to_conda_lookups()

    lookups = {}
    for pypi_name, versions in pypi_to_conda.items():
        # Simplify: extract just the conda package names
        simplified_versions: dict[PyPIVersion, list[CondaPackageName]] = {}
        for pypi_version, conda_packages in versions.items():
            # Get unique conda package names
            conda_names = list(dict.fromkeys([pkg.name for pkg in conda_packages]))
            simplified_versions[pypi_version] = conda_names

        lookup = PyPIPackageLookup(
            channel=str(table.channel),
            pypi_name=pypi_name,
            conda_versions=simplified_versions,
        )
        lookups[pypi_name] = lookup

    return lookups
