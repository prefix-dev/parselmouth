from parselmouth.internals.artifact import (
    extract_artifact_mapping,
    extract_conda_name_from_filename,
    get_pypi_names_and_version,
)


def test_linux_dist_info():
    files = ["lib/python3.13/site-packages/numpy-2.0.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"numpy": "2.0.0"}


def test_noarch_dist_info():
    files = ["site-packages/foo-1.0.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"foo": "1.0.0"}


def test_windows_dist_info():
    files = ["Lib/site-packages/foo-1.0.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"foo": "1.0.0"}


def test_windows_lowercase_lib_dist_info():
    files = ["lib/site-packages/idyntree-15.1.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"idyntree": "15.1.0"}


def test_egg_info_in_site_packages():
    files = ["lib/python3.10/site-packages/foo-1.2.3.egg-info/PKG-INFO"]
    assert get_pypi_names_and_version(files) == {"foo": "1.2.3"}


def test_setuptools_vendor_excluded():
    files = [
        "lib/python3.13/site-packages/setuptools-75.0.0.dist-info/METADATA",
        "lib/python3.13/site-packages/setuptools/_vendor/zipp-3.19.2.dist-info/METADATA",
    ]
    assert get_pypi_names_and_version(files) == {"setuptools": "75.0.0"}


def test_bundled_python_excluded_regression_5917():
    """google-cloud-sdk ships a full bundled CPython under
    share/.../bundledpythonunix/. Its dist-info entries must not be reported
    as PyPI names provided by the conda package.

    Regression test for https://github.com/prefix-dev/pixi/issues/5917.
    """
    files = [
        "share/google-cloud-sdk-565.0.0-0/platform/bundledpythonunix/lib/python3.13/site-packages/grpcio-1.80.0.dist-info/METADATA",
        "share/google-cloud-sdk-565.0.0-0/platform/bundledpythonunix/lib/python3.13/site-packages/cryptography-43.0.1.dist-info/METADATA",
        "share/google-cloud-sdk-565.0.0-0/platform/bundledpythonunix/lib/python3.13/site-packages/cffi-1.17.1.dist-info/METADATA",
    ]
    assert get_pypi_names_and_version(files) == {}


def test_mixed_real_and_bundled():
    files = [
        "lib/python3.12/site-packages/realpkg-1.0.0.dist-info/METADATA",
        "share/some-tool/platform/bundledpythonunix/lib/python3.13/site-packages/grpcio-1.80.0.dist-info/METADATA",
        "opt/some-app/python/site-packages/other-2.0.0.dist-info/METADATA",
    ]
    assert get_pypi_names_and_version(files) == {"realpkg": "1.0.0"}


def test_extract_conda_name_from_filename_tar_bz2():
    assert (
        extract_conda_name_from_filename(
            "conda-package-handling-1.7.3-py39h5161555_1.tar.bz2"
        )
        == "conda-package-handling"
    )


def test_extract_conda_name_from_filename_conda():
    assert (
        extract_conda_name_from_filename("numpy-1.26.4-py311h64a7726_0.conda")
        == "numpy"
    )


def test_extract_conda_name_from_filename_with_hyphens():
    assert (
        extract_conda_name_from_filename(
            "my-awesome-package-2.0.0-py310h1234567_0.tar.bz2"
        )
        == "my-awesome-package"
    )


def test_extract_artifact_mapping_fallback_on_bad_filename():
    """When filename can't be parsed, fall back to artifact['name'] from index.json."""
    artifact = {
        "name": "numpy",
        "version": "1.26.4",
        "index": {"name": "numpy", "version": "1.26.4"},
        "about": {},
        "rendered_recipe": {
            "source": [
                {"url": "https://pypi.org/packages/source/n/numpy/numpy-1.26.4.tar.gz"}
            ]
        },
        "raw_recipe": "",
        "conda_build_config": {},
        "files": ["lib/python3.10/site-packages/numpy-1.26.4.dist-info/METADATA"],
        "metadata_version": 1,
    }
    # Invalid filename - not a conda package format
    package_name = "not-a-valid-filename.xyz"

    result = extract_artifact_mapping(artifact, package_name)
    assert result.conda_name == "numpy"
