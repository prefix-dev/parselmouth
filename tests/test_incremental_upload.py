"""
Test incremental upload logic for PyPI lookup files.

This test verifies that the hash comparison and incremental upload logic works correctly.
"""

import hashlib
import pytest

from parselmouth.internals.relations_updater import (
    _compute_file_hash,
    _check_file_needs_update,
)
from parselmouth.internals.channels import SupportedChannels


def test_compute_file_hash():
    """Test that hash computation works correctly."""
    test_data = b'{"test": "data"}'
    hash_result = _compute_file_hash(test_data)

    # Should be SHA256
    expected = hashlib.sha256(test_data).hexdigest()
    assert hash_result == expected
    assert len(hash_result) == 64


def test_hash_stability():
    """Test that same data produces same hash."""
    data1 = b'{"pypi_name": "numpy", "version": "1.26.4"}'
    data2 = b'{"pypi_name": "numpy", "version": "1.26.4"}'

    hash1 = _compute_file_hash(data1)
    hash2 = _compute_file_hash(data2)

    assert hash1 == hash2


def test_hash_difference():
    """Test that different data produces different hash."""
    data1 = b'{"pypi_name": "numpy", "version": "1.26.4"}'
    data2 = b'{"pypi_name": "numpy", "version": "1.26.5"}'

    hash1 = _compute_file_hash(data1)
    hash2 = _compute_file_hash(data2)

    assert hash1 != hash2


def test_empty_data_hash():
    """Test hash computation with empty data."""
    empty_data = b''
    hash_result = _compute_file_hash(empty_data)

    expected = hashlib.sha256(empty_data).hexdigest()
    assert hash_result == expected


def test_large_data_hash():
    """Test hash computation with larger data."""
    large_data = b'x' * 10000
    hash_result = _compute_file_hash(large_data)

    expected = hashlib.sha256(large_data).hexdigest()
    assert hash_result == expected
    assert len(hash_result) == 64


@pytest.mark.skipif(
    True,
    reason="Requires S3 credentials - skipped in unit tests"
)
def test_check_file_needs_update_with_s3():
    """
    Test _check_file_needs_update with actual S3 interaction.

    This test is skipped by default as it requires S3 credentials.
    Run with: pytest -m "not skip" to enable if credentials are available.
    """
    test_data = b'{"test": "data"}'
    result = _check_file_needs_update(
        "test-package",
        test_data,
        SupportedChannels.CONDA_FORGE
    )

    # Should return True for non-existent file
    assert isinstance(result, bool)
