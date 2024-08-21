import json
import os
import re
import sys

from parselmouth.channels import SupportedChannels
from parselmouth.conda_forge import get_all_archs_available, get_subdir_repodata
from parselmouth.s3 import s3_client


dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)


def main(
    output_dir: str = "output_index",
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
):
    subdirs = get_all_archs_available(channel)

    all_packages: list[tuple[str, str]] = []

    existing_mapping_data = s3_client.get_mapping()

    letters = set()

    for subdir in subdirs:
        repodatas = {}
        repodata = get_subdir_repodata(subdir, channel)

        repodatas.update(repodata["packages"])
        repodatas.update(repodata["packages.conda"])

        for package_name in repodatas:
            package = repodatas[package_name]
            sha256 = package["sha256"]

            if sha256 not in existing_mapping_data:
                all_packages.append(package_name)
                letters.add(f"{subdir}@{package_name[0]}")

    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/index.json", mode="w") as mapping_file:
        json.dump(existing_mapping_data, mapping_file)

    json_letters = json.dumps(list(letters))

    print(json_letters)


if __name__ == "__main__":
    channel = (
        SupportedChannels(sys.argv[1])
        if len(sys.argv) > 0
        else SupportedChannels.CONDA_FORGE
    )
    main(channel=channel)
