import json
import os
import re

from parselmouth.conda_forge import get_all_archs_available, get_subdir_repodata
from parselmouth.s3 import s3_client


dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)


def main(output_dir: str = "output_index"):
    subdirs = get_all_archs_available()

    all_packages: list[tuple[str, str]] = []

    existing_mapping_data = s3_client.get_mapping()

    letters = set()

    for subdir in subdirs:
        repodatas = {}
        repodata = get_subdir_repodata(subdir)

        repodatas.update(repodata["packages"])
        repodatas.update(repodata["packages.conda"])

        for idx, package_name in enumerate(repodatas):
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
    main()
