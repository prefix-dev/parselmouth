from pathlib import Path
import re
from packaging.version import parse
from parselmouth.internals.utils import normalize
from typing import Optional
from conda_forge_metadata.types import ArtifactData
import logging

from parselmouth.internals.s3 import MappingEntry


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
        file_path = Path(file_name)
        # sometimes, packages like setuptools have some stuff vendored
        # that our regex will catch:
        # site-packages/setuptools/_vendor/zipp-3.19.2.dist-info/RECORD
        # but in reality we don't want to include itages:
        if "_vendor" in file_path.parts or "_vendored" in file_path.parts:
            continue
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


def extract_artifact_mapping(artifact: ArtifactData, package_name: str) -> MappingEntry:
    pypi_names_and_versions = get_pypi_names_and_version(artifact["files"])
    pypi_normalized_names = (
        [name for name in pypi_names_and_versions] if pypi_names_and_versions else None
    )
    source: Optional[dict] = artifact["rendered_recipe"].get("source", None)
    is_direct_url: Optional[bool] = None

    if source and isinstance(source, list):
        source = artifact["rendered_recipe"]["source"][0]
        is_direct_url = check_if_is_direct_url(
            package_name,
            source.get("url"),
        )

    conda_name = artifact["name"]

    if not is_direct_url or not source:
        direct_url = None
    else:
        url = source.get("url", None)
        direct_url = [str(url)] if isinstance(url, str) else url

    return MappingEntry.model_validate(
        {
            "pypi_normalized_names": pypi_normalized_names,
            "versions": pypi_names_and_versions if pypi_names_and_versions else None,
            "conda_name": str(conda_name),
            "package_name": package_name,
            "direct_url": direct_url,
        }
    )
