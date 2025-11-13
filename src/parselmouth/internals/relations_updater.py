"""
Relations Table Updater

This module generates and uploads the package relations table and derived lookup files.

Main workflow:
1. Load existing Conda -> PyPI hash-based index from S3
2. Convert to normalized relations table (JSONL)
3. Upload master table to S3
4. Generate and upload PyPI -> Conda lookup files (derived from table)

This replaces the previous pypi_mapping.py approach with a table-based architecture.
"""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from tqdm import tqdm

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.package_relations import (
    RelationsTable,
    create_pypi_lookup_files,
)
from parselmouth.internals.s3 import s3_client
from parselmouth.internals.types import PyPIName

logger = logging.getLogger(__name__)


def generate_and_upload_relations_table(
    channel: SupportedChannels,
    upload: bool = True,
    output_dir: Optional[str] = None,
    s3: Optional["S3"] = None,
) -> RelationsTable:
    """
    Generate the relations table from existing Conda->PyPI index and optionally upload.

    Args:
        channel: The conda channel to process
        upload: If True, upload table and lookups to S3
        output_dir: If provided, save files locally to this directory
        s3: Optional S3 client (for testing). If None, uses global s3_client.

    Returns:
        The generated RelationsTable
    """
    logger.info(f"Starting relations table generation for channel: {channel}")

    # Use provided S3 client or global one
    s3_instance = s3 or s3_client

    # Step 1: Load existing Conda -> PyPI index
    logger.info("Downloading existing Conda -> PyPI index from S3...")
    existing_index = s3_instance.get_channel_index(channel=channel)

    if not existing_index:
        raise ValueError(f"No existing index found for channel {channel}")

    logger.info(f"Loaded index with {len(existing_index.root)} conda packages")

    # Step 2: Build relations table
    logger.info("Building relations table...")
    table = RelationsTable.from_conda_to_pypi_index(existing_index, channel)

    metadata = table.get_metadata()
    logger.info(
        f"Generated table: {metadata.total_relations} relations, "
        f"{metadata.unique_conda_packages} conda packages, "
        f"{metadata.unique_pypi_packages} PyPI packages"
    )

    # Step 3: Upload or save master table
    table_data = table.to_jsonl(compress=True)
    logger.info(f"Serialized table to {len(table_data)} bytes (gzipped JSONL)")

    if upload:
        logger.info("Uploading relations table to S3...")
        s3_instance.upload_relations_table(table_data, channel)

        logger.info("Uploading metadata...")
        s3_instance.upload_relations_metadata(metadata.model_dump(), channel)

    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)

        table_path = os.path.join(output_dir, f"{channel}_relations.jsonl.gz")
        with open(table_path, "wb") as f:
            f.write(table_data)
        logger.info(f"Saved table to {table_path}")

        metadata_path = os.path.join(output_dir, f"{channel}_metadata.json")
        with open(metadata_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))
        logger.info(f"Saved metadata to {metadata_path}")

    return table


def _compute_file_hash(data: bytes) -> str:
    """Compute SHA256 hash of file data for comparison."""
    return hashlib.sha256(data).hexdigest()


def _check_file_needs_update(
    pypi_name: PyPIName,
    new_data: bytes,
    channel: SupportedChannels,
    s3_instance,
) -> bool:
    """
    Check if a PyPI lookup file needs to be updated.

    Returns True if the file doesn't exist or has changed.
    """
    # Try to get existing file
    existing_data = s3_instance.get_pypi_lookup_file(pypi_name, channel)

    if existing_data is None:
        # File doesn't exist, needs upload
        return True

    # Compare hashes
    existing_hash = _compute_file_hash(existing_data)
    new_hash = _compute_file_hash(new_data)

    return existing_hash != new_hash


def generate_and_upload_pypi_lookups(
    table: RelationsTable,
    channel: SupportedChannels,
    upload: bool = True,
    output_dir: Optional[str] = None,
    max_workers: int = 50,
    skip_unchanged: bool = True,
    s3: Optional["S3"] = None,
) -> dict[PyPIName, bytes]:
    """
    Generate PyPI -> Conda lookup files from the relations table.

    These are derived views cached as individual JSON files for fast access.

    Args:
        table: The relations table to derive lookups from
        channel: The conda channel
        upload: If True, upload lookup files to S3
        output_dir: If provided, save files locally to this directory
        max_workers: Number of parallel upload threads
        skip_unchanged: If True, only upload changed files (default: True)
        s3: Optional S3 client (for testing). If None, uses global s3_client.

    Returns:
        Dict mapping PyPI package names to their serialized JSON data
    """
    logger.info("Generating PyPI -> Conda lookup files...")

    # Use provided S3 client or global one
    s3_instance = s3 or s3_client

    lookups = create_pypi_lookup_files(table)
    logger.info(f"Generated {len(lookups)} PyPI lookup files")

    # Serialize all lookups
    serialized = {
        pypi_name: lookup.to_json_bytes()
        for pypi_name, lookup in lookups.items()
    }

    if upload:
        if skip_unchanged:
            logger.info("Checking for changed files (incremental mode)...")

            # Check which files need updating
            files_to_upload = {}

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all comparison tasks
                check_futures = {
                    executor.submit(
                        _check_file_needs_update,
                        pypi_name,
                        data,
                        channel,
                        s3_instance,
                    ): (pypi_name, data)
                    for pypi_name, data in serialized.items()
                }

                # Collect results
                with tqdm(total=len(check_futures), desc="Checking files") as pbar:
                    for future in as_completed(check_futures):
                        pypi_name, data = check_futures[future]
                        try:
                            needs_update = future.result()
                            if needs_update:
                                files_to_upload[pypi_name] = data
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Failed to check {pypi_name}: {e}")
                            # On error, assume needs update
                            files_to_upload[pypi_name] = data
                            pbar.update(1)

            skipped_count = len(serialized) - len(files_to_upload)
            logger.info(
                f"Found {len(files_to_upload)} changed files, "
                f"skipping {skipped_count} unchanged files"
            )
        else:
            logger.info("Uploading all files (full mode)...")
            files_to_upload = serialized

        if files_to_upload:
            logger.info(f"Uploading {len(files_to_upload)} PyPI lookup files to S3...")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        s3_instance.upload_pypi_lookup_file,
                        pypi_name,
                        data,
                        channel,
                    ): pypi_name
                    for pypi_name, data in files_to_upload.items()
                }

                # Track progress and handle errors
                with tqdm(total=len(futures), desc="Uploading PyPI lookups") as pbar:
                    for future in as_completed(futures):
                        pypi_name = futures[future]
                        try:
                            future.result()
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Failed to upload lookup for {pypi_name}: {e}")
                            raise

            logger.info("PyPI lookup files uploaded successfully")
        else:
            logger.info("No files need uploading (all unchanged)")

    if output_dir:
        import os
        lookups_dir = os.path.join(output_dir, "pypi_lookups")
        os.makedirs(lookups_dir, exist_ok=True)

        for pypi_name, data in tqdm(serialized.items(), desc="Saving PyPI lookups"):
            lookup_path = os.path.join(lookups_dir, f"{pypi_name}.json")
            with open(lookup_path, "wb") as f:
                f.write(data)

        logger.info(f"Saved {len(serialized)} lookup files to {lookups_dir}")

    return serialized


def main(
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
    output_dir: Optional[str] = None,
    skip_unchanged: bool = True,
) -> None:
    """
    Main entry point for generating and uploading relations table and lookups.

    This is the production workflow that:
    1. Generates the master relations table
    2. Uploads it to S3 (single source of truth)
    3. Generates PyPI -> Conda lookup files
    4. Uploads lookup files to S3 (for fast access)

    Args:
        channel: The conda channel to process
        upload: If True, upload to S3. If False, only save locally.
        output_dir: If provided, also save files locally
        skip_unchanged: If True, only upload changed lookup files (incremental mode)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 70)
    logger.info("RELATIONS TABLE UPDATER")
    logger.info(f"Channel: {channel}")
    logger.info(f"Upload to S3: {upload}")
    logger.info(f"Save locally: {output_dir or 'No'}")
    logger.info(f"Incremental mode: {skip_unchanged}")
    logger.info("=" * 70)

    # Generate and upload master table
    table = generate_and_upload_relations_table(
        channel=channel,
        upload=upload,
        output_dir=output_dir,
    )

    # Generate and upload derived PyPI lookup files
    generate_and_upload_pypi_lookups(
        table=table,
        channel=channel,
        upload=upload,
        output_dir=output_dir,
        skip_unchanged=skip_unchanged,
    )

    logger.info("=" * 70)
    logger.info("COMPLETED SUCCESSFULLY")
    logger.info("=" * 70)


if __name__ == "__main__":
    main(channel=SupportedChannels.CONDA_FORGE, upload=False, output_dir="./output_relations")
