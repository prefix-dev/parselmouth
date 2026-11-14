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


def _relation(
    conda_name: str,
    pypi_name: str = "tzdata",
    pypi_version: str = "2022.1",
) -> PackageRelation:
    return PackageRelation(
        conda_name=conda_name,
        conda_filename=f"{conda_name}-1.0.0-py311h_0.conda",
        conda_hash="a" * 64,
        pypi_name=pypi_name,
        pypi_version=pypi_version,
        channel="conda-forge",
    )


class TestPrefixStrippingAndThreshold:
    """Tests for conda name-prefix stripping and the Levenshtein threshold.

    These guard against wrong mappings like tzdata -> psycopg, where a conda
    package merely bundles a PyPI package under an unrelated name.
    """

    def test_tzdata_prefers_python_tzdata_over_psycopg(self):
        """python-tzdata (stripped to "tzdata", dist 0) beats psycopg (dist 7)."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            _relation("psycopg"),
            _relation("python-tzdata"),
            _relation("rosco"),
        ]

        lookups = create_pypi_lookup_files(table)
        assert lookups["tzdata"].conda_versions["2022.1"] == "python-tzdata"

    def test_tzdata_only_psycopg_is_omitted(self):
        """psycopg is too far (dist 7) from tzdata, so no mapping is served."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [_relation("psycopg")]

        lookups = create_pypi_lookup_files(table)
        assert "tzdata" not in lookups

    def test_tzdata_only_rosco_is_omitted(self):
        """rosco is too far (dist 6) from tzdata, so no mapping is served."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [_relation("rosco")]

        lookups = create_pypi_lookup_files(table)
        assert "tzdata" not in lookups

    def test_python_dateutil_exact_match_preserved(self):
        """Stripping "python-" from both sides keeps python-dateutil exact."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            PackageRelation(
                conda_name="python-dateutil",
                conda_filename="python-dateutil-2.9.0-py311h_0.conda",
                conda_hash="a" * 64,
                pypi_name="python-dateutil",
                pypi_version="2.9.0",
                channel="conda-forge",
            ),
        ]

        lookups = create_pypi_lookup_files(table)
        assert lookups["python-dateutil"].conda_versions["2.9.0"] == "python-dateutil"

    def test_exact_match_preferred_over_prefixed(self):
        """When both "foo" and "python-foo" provide PyPI "foo", exact "foo" wins."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            _relation("python-foo", pypi_name="foo"),
            _relation("foo", pypi_name="foo"),
        ]

        lookups = create_pypi_lookup_files(table)
        assert lookups["foo"].conda_versions["2022.1"] == "foo"

    def test_matplotlib_only_finesse_is_omitted(self):
        """finesse is too far from matplotlib, so no mapping is served."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            PackageRelation(
                conda_name="finesse",
                conda_filename="finesse-1.0.0-py311h_0.conda",
                conda_hash="a" * 64,
                pypi_name="matplotlib",
                pypi_version="3.9.0rc2",
                channel="conda-forge",
            ),
        ]

        lookups = create_pypi_lookup_files(table)
        assert "matplotlib" not in lookups

    def test_phantom_pypi_names_are_omitted(self):
        """PyPI names that don't exist on PyPI are never served as mappings."""
        table = RelationsTable(SupportedChannels.CONDA_FORGE)
        table.relations = [
            _relation("zaber-motion", pypi_name="zaber-bson"),
            _relation("alpenglow", pypi_name="alpenglow-sip"),
            _relation("ambertools", pypi_name="amberutils"),
            _relation(
                "felyxcontrib-metrics-workflow",
                pypi_name="felyxcontribs-metrics-workflow",
            ),
            _relation("gw-sklearn-xarray", pypi_name="sklearn-xarray"),
        ]

        lookups = create_pypi_lookup_files(table)
        for suppressed in (
            "zaber-bson",
            "alpenglow-sip",
            "amberutils",
            "felyxcontribs-metrics-workflow",
            "sklearn-xarray",
        ):
            assert suppressed not in lookups
