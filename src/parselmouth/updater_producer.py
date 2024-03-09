import json
import os
import re
import requests
import logging
import boto3
from dotenv import load_dotenv


dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)


load_dotenv()

account_id = os.environ["R2_PREFIX_ACCOUNT_ID"]
access_key_id = os.environ["R2_PREFIX_ACCESS_KEY_ID"]
access_key_secret = os.environ["R2_PREFIX_SECRET_ACCESS_KEY"]
bucket_name = os.environ["R2_PREFIX_BUCKET"]


def get_all_archs_available() -> set[str]:
    response = requests.get("https://conda.anaconda.org/conda-forge/channeldata.json")
    channel_json = response.json()
    # Collect all subdirectories
    subdirs: list[str] = []
    for package in channel_json["packages"].values():
        subdirs.extend(package.get("subdirs", []))

    return list(set(subdirs))


def get_subdir_repodata(subdir: str) -> dict:
    url = f"https://conda.anaconda.org/conda-forge/{subdir}/repodata.json"
    response = requests.get(url)
    if response.ok:
        return response.json()

    logging.error(f"Requst for repodata to {url} failed. {response.reason}")


if __name__ == "__main__":
    subdirs = get_all_archs_available()

    all_packages: list[tuple[str, str]] = []

    s3_client = boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=f"{access_key_id}",
        aws_secret_access_key=f"{access_key_secret}",
        region_name="eeur",  # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    index_obj_key = "hash-v0/index.json"
    response = s3_client.get_object(Bucket=bucket_name, Key=index_obj_key)
    existing_mapping_data = json.loads(response["Body"].read().decode("utf-8"))

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

    total = 0
    log_once = False

    os.makedirs("output_index", exist_ok=True)
    with open("output_index/index.json", mode="w") as mapping_file:
        json.dump(existing_mapping_data, mapping_file)

    print(json.dumps(list(letters)))
