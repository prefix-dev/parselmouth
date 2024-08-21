import re
from typing import Optional
import logging
from packaging.version import parse
from parselmouth.internals.conda_forge import (
    get_all_packages_by_subdir,
    get_artifact_info,
)
from parselmouth.internals.s3 import s3_client
from parselmouth.internals.utils import normalize
from rich import print


names_mapping: dict[str, dict] = {}

dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)


def check_if_is_direct_url(package_name: str, url: Optional[str]) -> bool:
    if not url:
        return False
    urls = None
    if not isinstance(url, str):
        logging.warning(f"{package_name} contains multiple urls")
        urls = url
    else:
        urls = list(url)

    if all(
        url.startswith("https://pypi.io/packages/")
        or url.startswith("https://pypi.org/packages/")
        or url.startswith("https://pypi.python.org/packages/")
        for url in urls
    ):
        return False

    return True


def get_pypi_names_and_version(files: list[str]) -> dict[str, str]:
    """
    Return a dictionary of normalized names to it's version
    """
    package_names: dict[str, str] = {}
    for file_name in files:
        match = dist_pattern_compiled.search(file_name) or egg_pattern_compiled.search(
            file_name
        )
        if match:
            package_name = match.group(1)
            if not package_name:
                continue

            version = match.group(2)
            if "-py" in version:
                index_of_py = version.index("-py")
                version = version[:index_of_py]

            pkg_version = None

            try:
                pkg_version = parse(version)
            except Exception:
                if "-" in version:
                    index_of_dash = version.rfind("-")
                    version = version[:index_of_dash]

            if pkg_version:
                version = str(pkg_version)

            package_names[normalize(package_name)] = version

    return package_names


def main(
    package_name: str,
    subdir: str,
    backend_type: None | str = None,
    upload: bool = False,
):
    repodatas = get_all_packages_by_subdir(subdir)

    found_sha = None

    for repodata_package_name in repodatas:
        if repodata_package_name == package_name:
            found_sha = repodatas[package_name]["sha256"]
            break

    if not found_sha:
        raise ValueError(
            f"Could not find the package {package_name} in the repodata for subdir {subdir}"
        )

    names_mapping = {}
    backend_types = (
        [backend_type] if backend_type else ["oci", "streamed", "libcfgraph"]
    )
    for backend_type in backend_types:
        artifact = get_artifact_info(
            subdir=subdir, artifact=package_name, backend=backend_type
        )
        if artifact:
            pypi_names_and_versions = get_pypi_names_and_version(artifact["files"])
            pypi_normalized_names = (
                [name for name in pypi_names_and_versions]
                if pypi_names_and_versions
                else None
            )
            source: Optional[dict] = artifact["rendered_recipe"].get("source", None)
            is_direct_url: Optional[bool] = None

            if source and isinstance(source, list):
                source = artifact["rendered_recipe"]["source"][0]
                is_direct_url = check_if_is_direct_url(
                    package_name,
                    source.get("url"),
                )

            sha = repodatas[package_name]["sha256"]
            conda_name = artifact["name"]

            if not is_direct_url or not source:
                direct_url = None
            else:
                url = source.get("url", None)
                direct_url = [url] if isinstance(url, str) else url

            if sha not in names_mapping:
                names_mapping[sha] = {
                    "pypi_normalized_names": pypi_normalized_names,
                    "versions": pypi_names_and_versions
                    if pypi_names_and_versions
                    else None,
                    "conda_name": conda_name,
                    "package_name": package_name,
                    "direct_url": direct_url,
                }
            break

    if not names_mapping:
        raise Exception(f"Could not get artifact for {package_name} using any backend")

    print(names_mapping)

    if upload:
        logging.warning("Uploading mapping to S3")
        for sha_name, mapping_body in names_mapping.items():
            s3_client.upload_mapping(mapping_body, sha_name)
