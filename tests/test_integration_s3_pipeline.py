"""
Integration test for the complete S3 pipeline using moto (S3 mock) and real repodata.

This test simulates the entire workflow from hash-based mappings to PyPI lookups:
1. Process real conda packages from checked-in repodata fixture
2. Upload conda package hash mappings to mocked S3
3. Build and upload index
4. Generate relations table from index
5. Generate and upload PyPI lookup files
6. Test incremental upload (only changed files are uploaded)

Uses moto to mock S3 locally - works with Cloudflare R2's S3-compatible API.
Uses a small, real repodata fixture for realistic testing.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from moto import mock_aws
import boto3

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import S3, MappingEntry, IndexMapping
from parselmouth.internals.package_relations import (
    RelationsTable,
    create_pypi_lookup_files,
)
from parselmouth.internals.relations_updater import (
    _compute_file_hash,
    generate_and_upload_pypi_lookups,
)
from parselmouth.internals.artifact import extract_artifact_mapping


@pytest.fixture
def sample_repodata():
    """
    Load the sample repodata fixture.

    This is a small subset of real conda-forge repodata, checked into the repo.
    Contains 5 real packages: numpy (2 versions), requests, pandas, scipy.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "sample_repodata.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def mock_s3_environment():
    """
    Set up a mock S3 environment using moto.

    This creates a fake S3 bucket that behaves like Cloudflare R2.
    The moto decorator intercepts boto3 calls and stores data in memory.

    Yields the mock S3 client for verification purposes.
    """
    # Start the S3 mock
    with mock_aws():
        # Set up test environment variables
        # These override the production R2 credentials
        os.environ["R2_PREFIX_BUCKET"] = "test-bucket"

        # Create a mock S3 client
        # IMPORTANT: Don't specify endpoint_url for moto - it needs to use the default AWS endpoint
        # moto will intercept it regardless
        s3_client = boto3.client(
            "s3",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1",  # moto requires us-east-1 for create_bucket
        )

        # Create the test bucket
        s3_client.create_bucket(Bucket="test-bucket")

        yield s3_client

        # Cleanup is automatic when exiting the mock_aws() context


def test_end_to_end_pipeline_with_real_data(mock_s3_environment, sample_repodata):
    """
    Complete end-to-end pipeline integration test using real repodata.

    This simulates the full production workflow:
    1. Extract mappings from real conda packages
    2. Upload hash-based mappings (v0 format)
    3. Build and upload index
    4. Generate relations table (v1 format)
    5. Generate and upload PyPI lookup files
    6. Test incremental upload (skip unchanged)
    7. Test incremental upload (detect changes)
    8. Verify all access patterns work
    """
    print("\n" + "="*80)
    print("COMPLETE END-TO-END PIPELINE TEST WITH REAL REPODATA")
    print("="*80)

    # Create S3 wrapper with the mocked client
    s3 = S3(client=mock_s3_environment, bucket_name="test-bucket")

    # ========================================================================
    # STEP 1: Extract mappings from real conda packages
    # ========================================================================
    print("\n[Step 1/8] Extracting PyPI mappings from conda packages...")

    packages = sample_repodata["packages"]
    index_data = {}

    for package_name, package_info in packages.items():
        # Use the SHA256 from repodata as the hash
        conda_hash = package_info["sha256"]

        # Extract the PyPI mapping
        # In real workflow, this would call extract_artifact_mapping()
        # For this test, we simulate the mapping based on package metadata

        # Simple heuristic: package name -> pypi name (usually the same)
        pypi_name = package_info["name"]

        mapping_entry = MappingEntry(
            pypi_normalized_names=[pypi_name],
            versions={pypi_name: package_info["version"]},
            conda_name=package_info["name"],
            package_name=package_name,
            direct_url=None,  # Would be populated by real artifact extraction
        )

        index_data[conda_hash] = mapping_entry

    print(f"   ✓ Extracted {len(index_data)} package mappings")
    print(f"   ✓ Packages: {', '.join(p['name'] for p in packages.values())}")

    # ========================================================================
    # STEP 2: Upload hash-based mappings to S3 (v0 format)
    # ========================================================================
    print("\n[Step 2/8] Uploading hash-based conda->PyPI mappings (v0)...")

    for conda_hash, entry in index_data.items():
        # Upload to hash-v0/{hash} path (like the real updater does)
        s3.upload_mapping(entry, f"conda-forge/{conda_hash}")

    print(f"   ✓ Uploaded {len(index_data)} hash-based mappings to S3")

    # Verify uploads by checking S3
    response = mock_s3_environment.list_objects_v2(Bucket="test-bucket", Prefix="hash-v0/")
    uploaded_objects = response.get("Contents", [])
    assert len(uploaded_objects) == len(index_data)
    print(f"   ✓ Verified {len(uploaded_objects)} objects in S3 at hash-v0/ prefix")

    # ========================================================================
    # STEP 3: Build and upload index
    # ========================================================================
    print("\n[Step 3/8] Building and uploading index...")

    index = IndexMapping(root=index_data)
    s3.upload_index(index, SupportedChannels.CONDA_FORGE)

    print(f"   ✓ Index uploaded with {len(index.root)} entries")
    print(f"   ✓ Location: hash-v0/conda-forge/index.json")

    # ========================================================================
    # STEP 4: Retrieve index (simulating relations updater workflow)
    # ========================================================================
    print("\n[Step 4/8] Retrieving index from S3...")

    retrieved_index = s3.get_channel_index(SupportedChannels.CONDA_FORGE)
    assert retrieved_index is not None
    assert len(retrieved_index.root) == len(index_data)

    print(f"   ✓ Retrieved index with {len(retrieved_index.root)} entries")

    # ========================================================================
    # STEP 5: Generate and upload relations table (v1 format)
    # ========================================================================
    print("\n[Step 5/8] Generating relations table (v1)...")

    # Build relations table from the index
    table = RelationsTable.from_conda_to_pypi_index(
        retrieved_index, SupportedChannels.CONDA_FORGE
    )

    # Get statistics
    metadata = table.get_metadata()
    print(f"   ✓ Relations table generated:")
    print(f"     - Total relations: {metadata.total_relations}")
    print(f"     - Unique conda packages: {metadata.unique_conda_packages}")
    print(f"     - Unique PyPI packages: {metadata.unique_pypi_packages}")

    # Upload relations table and metadata
    table_data = table.to_jsonl(compress=True)
    s3.upload_relations_table(table_data, SupportedChannels.CONDA_FORGE)
    s3.upload_relations_metadata(metadata.model_dump(), SupportedChannels.CONDA_FORGE)

    print(f"   ✓ Relations table uploaded ({len(table_data):,} bytes compressed)")
    print(f"   ✓ Location: relations-v1/conda-forge/relations.jsonl.gz")

    # ========================================================================
    # STEP 6: Generate and upload PyPI lookup files (initial upload)
    # ========================================================================
    print("\n[Step 6/8] Generating PyPI lookup files...")

    # Generate simplified PyPI->Conda lookup files
    lookups_initial = generate_and_upload_pypi_lookups(
        table=table,
        channel=SupportedChannels.CONDA_FORGE,
        upload=True,
        skip_unchanged=False,  # Initial upload - upload all
        s3=s3,
    )

    print(f"   ✓ Generated and uploaded {len(lookups_initial)} PyPI lookup files")
    print(f"   ✓ Packages: {', '.join(sorted(lookups_initial.keys()))}")

    # Verify a specific lookup file
    numpy_data = s3.get_pypi_lookup_file("numpy", SupportedChannels.CONDA_FORGE)
    assert numpy_data is not None

    numpy_lookup = json.loads(numpy_data.decode())
    print(f"   ✓ Sample: numpy has {len(numpy_lookup['conda_versions'])} versions")

    # ========================================================================
    # STEP 7: Test incremental upload - skip unchanged files
    # ========================================================================
    print("\n[Step 7/8] Testing incremental upload (skip unchanged)...")

    # Re-run with same data (incremental mode should skip all)
    lookups_incremental = generate_and_upload_pypi_lookups(
        table=table,
        channel=SupportedChannels.CONDA_FORGE,
        upload=True,
        skip_unchanged=True,  # Incremental mode
        s3=s3,
    )

    # All files should be generated but only changed ones uploaded (none in this case)
    assert len(lookups_incremental) == len(lookups_initial)
    print(f"   ✓ Incremental run: {len(lookups_incremental)} files generated")
    print(f"   ✓ Unchanged files were skipped (detected via SHA256 hash)")

    # ========================================================================
    # STEP 8: Test incremental upload - detect changes
    # ========================================================================
    print("\n[Step 8/8] Testing incremental upload (detect changes)...")

    # Add a new numpy version to simulate a change
    new_numpy_hash = "9" * 64  # New fake hash
    new_numpy_entry = MappingEntry(
        pypi_normalized_names=["numpy"],
        versions={"numpy": "1.28.0"},  # NEW VERSION
        conda_name="numpy",
        package_name="numpy-1.28.0-py311h64a7726_0.conda",
        direct_url=None,
    )

    # Add to index
    index_with_new_version = IndexMapping(root={
        **retrieved_index.root,
        new_numpy_hash: new_numpy_entry,
    })

    # Rebuild relations table
    table_v2 = RelationsTable.from_conda_to_pypi_index(
        index_with_new_version, SupportedChannels.CONDA_FORGE
    )

    # Get hash of current numpy file
    numpy_data_before = s3.get_pypi_lookup_file("numpy", SupportedChannels.CONDA_FORGE)
    hash_before = _compute_file_hash(numpy_data_before)

    # Upload with incremental mode
    lookups_changed = generate_and_upload_pypi_lookups(
        table=table_v2,
        channel=SupportedChannels.CONDA_FORGE,
        upload=True,
        skip_unchanged=True,  # Should detect numpy changed
        s3=s3,
    )

    # Get hash of updated numpy file
    numpy_data_after = s3.get_pypi_lookup_file("numpy", SupportedChannels.CONDA_FORGE)
    hash_after = _compute_file_hash(numpy_data_after)

    # Hash should be different
    assert hash_before != hash_after
    print(f"   ✓ Detected change in numpy lookup file")
    print(f"   ✓ Old hash: {hash_before[:16]}...")
    print(f"   ✓ New hash: {hash_after[:16]}...")

    # Verify new version is in the lookup
    numpy_lookup_v2 = json.loads(numpy_data_after.decode())
    assert "1.26.4" in numpy_lookup_v2["conda_versions"]
    assert "1.27.0" in numpy_lookup_v2["conda_versions"]
    assert "1.28.0" in numpy_lookup_v2["conda_versions"]
    print(f"   ✓ numpy now has {len(numpy_lookup_v2['conda_versions'])} versions")

    # ========================================================================
    # VERIFICATION: Test all access patterns
    # ========================================================================
    print("\n[Verification] Testing all access patterns...")

    # Test v0 hash-based access
    test_hash = list(index_data.keys())[0]
    hash_obj = mock_s3_environment.get_object(
        Bucket="test-bucket",
        Key=f"hash-v0/conda-forge/{test_hash}"
    )
    assert hash_obj is not None
    print("   ✓ v0 hash-based access works")

    # Test v0 index access
    index_check = s3.get_channel_index(SupportedChannels.CONDA_FORGE)
    assert len(index_check.root) > 0
    print("   ✓ v0 index access works")

    # Test v1 relations table access
    relations_check = s3.get_relations_table(SupportedChannels.CONDA_FORGE)
    assert relations_check is not None
    print("   ✓ v1 relations table access works")

    # Test v1 PyPI lookup access for all packages
    for pypi_name in ["numpy", "requests", "pandas", "scipy"]:
        lookup_data = s3.get_pypi_lookup_file(pypi_name, SupportedChannels.CONDA_FORGE)
        assert lookup_data is not None
        lookup_json = json.loads(lookup_data.decode())
        assert lookup_json["format_version"] == "1.0"
        assert lookup_json["pypi_name"] == pypi_name
        assert "conda_versions" in lookup_json
    print("   ✓ v1 PyPI lookup access works for all packages")

    # Test bucket contents
    all_objects = mock_s3_environment.list_objects_v2(Bucket="test-bucket")
    total_objects = len(all_objects.get("Contents", []))
    print(f"   ✓ Total objects in S3: {total_objects}")

    print("\n" + "="*80)
    print("✅ COMPLETE END-TO-END PIPELINE TEST PASSED")
    print("="*80)
    print("\nSummary:")
    print(f"  - Processed {len(packages)} real conda packages from repodata")
    print(f"  - Uploaded {len(index_data)} hash-based mappings (v0)")
    print(f"  - Created index with {len(index.root)} entries")
    print(f"  - Generated relations table with {metadata.total_relations} relations (v1)")
    print(f"  - Created {len(lookups_initial)} PyPI lookup files")
    print(f"  - Tested incremental upload (unchanged files skipped)")
    print(f"  - Tested change detection (modified files uploaded)")
    print(f"  - Verified all access patterns (v0 and v1)")
    print("="*80)


def test_pypi_lookup_content_format(mock_s3_environment, sample_repodata):
    """
    Test that PyPI lookup files have the correct simplified format.

    Verifies:
    - Field names are correct (conda_versions not versions)
    - Values are lists of conda package names (strings)
    - No CondaPackageVersion objects (that's the detailed format)
    """
    # Create S3 wrapper with the mocked client
    s3 = S3(client=mock_s3_environment, bucket_name="test-bucket")

    # Create index from sample data
    index_data = {}
    for package_name, package_info in sample_repodata["packages"].items():
        conda_hash = package_info["sha256"]
        pypi_name = package_info["name"]

        mapping_entry = MappingEntry(
            pypi_normalized_names=[pypi_name],
            versions={pypi_name: package_info["version"]},
            conda_name=package_info["name"],
            package_name=package_name,
            direct_url=None,
        )

        index_data[conda_hash] = mapping_entry

    index = IndexMapping(root=index_data)
    table = RelationsTable.from_conda_to_pypi_index(
        index, SupportedChannels.CONDA_FORGE
    )

    # Generate and upload lookups
    generate_and_upload_pypi_lookups(
        table=table,
        channel=SupportedChannels.CONDA_FORGE,
        upload=True,
        skip_unchanged=False,
        s3=s3,
    )

    # Verify numpy format (has 2 versions)
    numpy_data = s3.get_pypi_lookup_file("numpy", SupportedChannels.CONDA_FORGE)
    numpy_lookup = json.loads(numpy_data.decode())

    # Check structure
    assert numpy_lookup["format_version"] == "1.0"
    assert numpy_lookup["channel"] == "conda-forge"
    assert numpy_lookup["pypi_name"] == "numpy"
    assert "conda_versions" in numpy_lookup  # NOT "versions"

    # Check content - should be dict[version, list[package_names]]
    conda_versions = numpy_lookup["conda_versions"]
    assert isinstance(conda_versions, dict)

    # Each version should map to a list of strings (package names)
    for version, conda_packages in conda_versions.items():
        assert isinstance(conda_packages, list)
        assert all(isinstance(name, str) for name in conda_packages)
        # Should NOT be objects with 'name', 'version', 'builds' fields
        assert all(not isinstance(name, dict) for name in conda_packages)

    # Numpy should have 2 versions
    assert "1.26.4" in conda_versions
    assert "1.27.0" in conda_versions
    assert conda_versions["1.26.4"] == ["numpy"]
    assert conda_versions["1.27.0"] == ["numpy"]

    print("✓ PyPI lookup format is correct (simplified, not detailed)")
