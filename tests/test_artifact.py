from parselmouth.internals.artifact import get_pypi_names_and_version


def test_linux_dist_info():
    files = ["lib/python3.13/site-packages/numpy-2.0.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"numpy": "2.0.0"}


def test_noarch_dist_info():
    files = ["site-packages/foo-1.0.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"foo": "1.0.0"}


def test_windows_dist_info():
    files = ["Lib/site-packages/foo-1.0.0.dist-info/METADATA"]
    assert get_pypi_names_and_version(files) == {"foo": "1.0.0"}


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
