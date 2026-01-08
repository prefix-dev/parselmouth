"""Tests for Levenshtein distance and best-match selection logic."""

from parselmouth.internals.package_relations import (
    levenshtein_distance,
    create_pypi_lookup_files,
    RelationsTable,
    PackageRelation,
)
from parselmouth.internals.channels import SupportedChannels


class TestLevenshteinDistance:
    """Test the Levenshtein distance implementation."""

    def test_identical_strings(self):
        assert levenshtein_distance("numpy", "numpy") == 0

    def test_empty_strings(self):
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("abc", "") == 3
        assert levenshtein_distance("", "abc") == 3

    def test_single_insertion(self):
        assert levenshtein_distance("numpy", "numpyy") == 1

    def test_single_deletion(self):
        assert levenshtein_distance("numpy", "nump") == 1

    def test_single_substitution(self):
        assert levenshtein_distance("numpy", "numpi") == 1

    def test_numpy_vs_numpy_base(self):
        # "numpy" vs "numpy-base" should prefer "numpy"
        assert levenshtein_distance("numpy", "numpy") == 0
        assert levenshtein_distance("numpy", "numpy-base") == 5

    def test_requests_variants(self):
        # "requests" should be closer to "requests" than to "requests-toolbelt"
        assert levenshtein_distance("requests", "requests") == 0
        assert levenshtein_distance("requests", "requests-toolbelt") == 9

    def test_case_sensitive(self):
        # Levenshtein is case-sensitive
        assert levenshtein_distance("NumPy", "numpy") == 2


class TestBestMatchSelection:
    """Test that the best match is selected correctly using Levenshtein distance."""

    def test_selects_exact_match(self):
        """When an exact match exists, it should be selected."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            PackageRelation(
                conda_name="numpy",
                conda_filename="numpy-1.26.4-py311h_0.conda",
                conda_hash="a" * 64,
                pypi_name="numpy",
                pypi_version="1.26.4",
                channel="conda-forge",
            ),
            PackageRelation(
                conda_name="numpy-base",
                conda_filename="numpy-base-1.26.4-py311h_0.conda",
                conda_hash="b" * 64,
                pypi_name="numpy",
                pypi_version="1.26.4",
                channel="conda-forge",
            ),
        ]

        lookups = create_pypi_lookup_files(table)
        assert "numpy" in lookups
        # Should select "numpy" (distance 0) over "numpy-base" (distance 5)
        assert lookups["numpy"].conda_versions["1.26.4"] == "numpy"

    def test_selects_closest_match(self):
        """When no exact match exists, select the closest one."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            PackageRelation(
                conda_name="py-numpy",
                conda_filename="py-numpy-1.26.4-py311h_0.conda",
                conda_hash="a" * 64,
                pypi_name="numpy",
                pypi_version="1.26.4",
                channel="conda-forge",
            ),
            PackageRelation(
                conda_name="python-numpy-extended",
                conda_filename="python-numpy-extended-1.26.4-py311h_0.conda",
                conda_hash="b" * 64,
                pypi_name="numpy",
                pypi_version="1.26.4",
                channel="conda-forge",
            ),
        ]

        lookups = create_pypi_lookup_files(table)
        assert "numpy" in lookups
        # "py-numpy" (distance 3) should be selected over "python-numpy-extended" (distance 16)
        assert lookups["numpy"].conda_versions["1.26.4"] == "py-numpy"
