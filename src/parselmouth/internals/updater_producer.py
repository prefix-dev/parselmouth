import json
import os
from pathlib import Path
import re

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.conda_forge import (
    get_all_archs_available,
    get_subdir_repodata,
)
from parselmouth.internals.s3 import IndexMapping, s3_client


dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)


def main(output_dir: str, force: bool, channel: SupportedChannels):
    subdirs = get_all_archs_available(channel)

    all_packages: list[tuple[str, str]] = []

    existing_mapping_data = s3_client.get_channel_index(channel=channel)
    if not existing_mapping_data:
        existing_mapping_data = IndexMapping(root={})

    letters = set()

    for subdir in subdirs:
        repodatas = {}
        repodata = get_subdir_repodata(subdir, channel)

        repodatas.update(repodata["packages"])
        repodatas.update(repodata["packages.conda"])

        for package_name in repodatas:
            package = repodatas[package_name]
            sha256 = package["sha256"]

            if force:
                all_packages.append(package_name)
                letters.add(f"{subdir}@{package_name[0]}")

            elif sha256 not in existing_mapping_data.root:
                all_packages.append(package_name)
                letters.add(f"{subdir}@{package_name[0]}")

    index_location = Path(output_dir) / channel / "index.json"
    os.makedirs(index_location.parent, exist_ok=True)

    with open(index_location, mode="w") as mapping_file:
        json.dump(existing_mapping_data.model_dump(), mapping_file)

    json_letters = json.dumps(list(letters))

    print(json_letters)
