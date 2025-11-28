"""
Test the relations table with real production data (no S3 credentials needed).

This script:
1. Downloads the production index.json via HTTPS (public URL)
2. Builds the relations table locally
3. Saves all output files locally
4. No S3 writes - completely safe!
"""

from pathlib import Path
import requests
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.package_relations import (
    RelationsTable,
    create_pypi_lookup_files,
)
from parselmouth.internals.s3 import IndexMapping


def main() -> None:
    print("=" * 70)
    print("TESTING WITH REAL PRODUCTION DATA")
    print("=" * 70)

    # Step 1: Download production index via HTTPS (no credentials needed)
    print("\n1. Downloading production index from public URL...")
    index_url = "https://conda-mapping.prefix.dev/hash-v0/conda-forge/index.json"
    print(f"   URL: {index_url}")

    try:
        response = requests.get(index_url, timeout=60)
        response.raise_for_status()
        index_data = response.json()
        print(f"   ✓ Downloaded {len(index_data)} conda packages")
    except Exception as e:
        print(f"   ✗ Failed to download: {e}")
        print("\nAlternative: Download manually and save to /tmp/index.json")
        print(f"   curl {index_url} -o /tmp/index.json")
        exit(1)

    # Step 2: Load into IndexMapping
    print("\n2. Loading index into data model...")
    index = IndexMapping(root=index_data)
    print(f"   ✓ Loaded {len(index.root)} packages")

    # Step 3: Build relations table
    print("\n3. Building relations table...")
    table = RelationsTable.from_conda_to_pypi_index(
        index, SupportedChannels.CONDA_FORGE
    )
    metadata = table.get_metadata()
    print("   ✓ Created table:")
    print(f"     - Total relations: {metadata.total_relations:,}")
    print(f"     - Unique conda packages: {metadata.unique_conda_packages:,}")
    print(f"     - Unique PyPI packages: {metadata.unique_pypi_packages:,}")

    # Step 4: Serialize table
    print("\n4. Serializing table to JSONL...")
    table_data = table.to_jsonl(compress=True)
    print(
        f"   ✓ Compressed size: {len(table_data):,} bytes ({len(table_data)/1024/1024:.1f} MB)"
    )

    # Step 5: Generate lookup files
    print("\n5. Generating PyPI lookup files...")
    lookup_files = create_pypi_lookup_files(table)
    print(f"   ✓ Generated {len(lookup_files):,} lookup files")

    # Step 6: Save everything locally
    output_dir = Path("./test_production")
    output_dir.mkdir(exist_ok=True)
    lookups_dir = output_dir / "pypi_lookups"
    lookups_dir.mkdir(exist_ok=True)

    print(f"\n6. Saving files to {output_dir}/...")

    # Save table
    table_path = output_dir / "relations.jsonl.gz"
    with open(table_path, "wb") as f:
        f.write(table_data)
    print(f"   ✓ {table_path.name} ({len(table_data):,} bytes)")

    # Save metadata
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        f.write(metadata.model_dump_json(indent=2))
    print(f"   ✓ {metadata_path.name}")

    # Save lookup files (first 10 for quick test)
    print("\n   Saving lookup files (showing first 10)...")
    saved_count = 0
    for pypi_name, lookup in lookup_files.items():
        lookup_path = lookups_dir / f"{pypi_name}.json"
        with open(lookup_path, "wb") as f:
            f.write(lookup.to_json_bytes())

        if saved_count < 10:
            print(f"     - {lookup_path.name}")
        saved_count += 1

    print(f"\n   ✓ Saved all {saved_count:,} lookup files")


if __name__ == "__main__":
    main()
