import re
from typing import Optional
import logging
from parselmouth.internals.artifact import extract_artifact_mapping
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.conda_forge import (
    get_all_packages_by_subdir,
    get_artifact_info,
)
from parselmouth.internals.s3 import MappingEntry, s3_client
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


def main(
    package_name: str,
    subdir: str,
    backend_type: None | str = None,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
):
    repodatas = get_all_packages_by_subdir(subdir, channel)

    found_sha = None
    repodata_by_label = None
    for label, packages in repodatas.items():
        if package_name in packages:
            repodata_by_label = packages
            found_sha = packages[package_name]["sha256"]
            break

    if not found_sha or not repodata_by_label:
        raise ValueError(
            f"Could not find the package {package_name} in the repodata for subdir {subdir}"
        )

    names_mapping: dict[str, MappingEntry] = {}
    backend_types = (
        [backend_type] if backend_type else ["oci", "streamed", "libcfgraph"]
    )
    for backend_type in backend_types:
        artifact = get_artifact_info(
            subdir=subdir, artifact=package_name, backend=backend_type, channel=channel
        )
        if artifact:
            sha = repodata_by_label[package_name]["sha256"]
            if sha not in names_mapping:
                mapping_entry = extract_artifact_mapping(artifact, package_name)
                names_mapping[sha] = mapping_entry
            break

    if not names_mapping:
        raise Exception(f"Could not get artifact for {package_name} using any backend")

    print(names_mapping)

    if upload:
        # getting the index mapping
        existing_mapping_data = s3_client.get_channel_index(channel=channel)
        if not existing_mapping_data:
            raise ValueError(f"Could not get the index mapping for channel {channel}")

        # updating with the new mapping
        existing_mapping_data.root.update(names_mapping)

        logging.warning("Uploading index to S3")
        s3_client.upload_index(existing_mapping_data, channel=channel)

        logging.warning("Uploading mapping to S3")
        for sha_name, mapping_body in names_mapping.items():
            s3_client.upload_mapping(mapping_body, sha_name)
