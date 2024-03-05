import json
import shutil
import sys
import os
import re
import itertools
from typing import Optional
import requests
from conda_forge_metadata.artifact_info import get_artifact_info_as_json
import concurrent.futures
import logging
import boto3
from conda_oci_mirror.defaults import CACHE_DIR

names_mapping: dict[str, str] = {}

dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)

# MAPPING = "mapping.json"

account_id = os.environ['R2_ACCOUNT_ID']
access_key_id = os.environ['R2_ACCESS_KEY_ID']
access_key_secret = os.environ['R2_SECRET_ACCESS_KEY']
bucket_name = os.environ['R2_BUCKET']


def normalize(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return re.sub(r"[-_.]+", "-", name).lower()


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


def get_pypi_names_and_version(pkg_name: str, files: str) -> dict[str, str]:
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
            version = match.group(2)
            if '-py' in version:
                index_of_py = version.index('-py')
                version = version[:index_of_py]

            package_names[normalize(package_name)] = version

    return package_names


if __name__ == "__main__":
    # subdir, letter = sys.argv[1].split("@")

    subdirs = get_all_archs_available()
    # subdirs = ["noarch"]
    
    # repodata = get_subdir_repodata("osx-arm64")
        
    all_packages: list[tuple[str, str]] = []


    s3_client = boto3.client(
        service_name ="s3",
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id = f"{access_key_id}",
        aws_secret_access_key = f"{access_key_secret}",
        region_name="eeur", # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    # obj_key = f"output/hashes-v1/all/mapping-cleaned.json"
    # response = s3_client.get_object(Bucket=bucket_name, Key=obj_key)
    # existing_mapping_data = json.loads(response['Body'].read().decode('utf-8'))

    with open('new_mapping.json') as ff:
        existing_mapping_data = json.load(ff)

    # sys.stdout = open(os.devnull, 'w')

    repodatas = {}

    for subdir in subdirs:
        repodata = get_subdir_repodata(subdir)

        repodatas.update(repodata["packages"])
        repodatas.update(repodata["packages.conda"])


    # if "packages" not in repodata:
    #     logging.warning(f"Repodata for {subdir} does not contain any packages")
    #     sys.exit(1)
    # else:
        
    for idx, package_name in enumerate(repodatas):
        # if not package_name.startswith(letter):
        #     continue

        package = repodatas[package_name]
        # import pdb; pdb.set_trace()
        sha256 = package["sha256"]

        if sha256 not in existing_mapping_data:
            all_packages.append((subdir, package_name))


    total = 0
    log_once = False
    print(f"Total is {len(all_packages)}")


    chunk_size = 50000
    chunks = [all_packages[i:i+chunk_size] for i in range(0,len(all_packages),chunk_size)]

    for chunk in chunks:

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    get_artifact_info_as_json,
                    channel="conda-forge",
                    subdir=subdir,
                    artifact=package_name,
                    backend="streamed" if package_name.endswith('.conda') else "oci",
                ): package_name
                for subdir, package_name in chunk
            }

            for done in concurrent.futures.as_completed(futures):
                total += 1
                if total % 5000 == 0:
                    print(f"Done {total} from {len(all_packages)}")
                package_name = futures[done]
                try:
                    artifact = done.result()
                    if artifact:
                        pypi_names_and_versions = get_pypi_names_and_version(package_name, artifact["files"])
                        pypi_normalized_names = (
                            [name for name in pypi_names_and_versions] if pypi_names_and_versions else None
                        )
                        source: Optional[dict] = artifact["rendered_recipe"].get("source", None)
                        is_direct_url: Optional[bool] = None

                        if source and isinstance(source, list):
                            source = artifact["rendered_recipe"]["source"][0]
                            is_direct_url = check_if_is_direct_url(
                                conda_name,
                                source.get("url"),
                            )


                        sha = repodatas[package_name]["sha256"]
                        conda_name = artifact["name"]

                        if not is_direct_url:
                            direct_url = None
                        else:
                            url = source.get("url", None)
                            direct_url = [url] if isinstance(url, str) else url

                        if sha not in names_mapping:
                            names_mapping[sha] = {
                                "pypi_normalized_names": pypi_normalized_names,
                                "versions": pypi_names_and_versions if pypi_names_and_versions else None,
                                "conda_name": conda_name,
                                "package_name": package_name,
                                "direct_url": direct_url,
                            }

                except Exception as e:
                    logging.error(f"An error occurred: {e} for package {package_name}")
        if not log_once:
            logging.error("cleaned")
            log_once = True
        
    print('done')
    #     if os.path.exists(CACHE_DIR):
    #         shutil.rmtree(CACHE_DIR)

    # existing_mapping_data.update(names_mapping)

    # os.makedirs(f"output/hashes-v1", exist_ok=True)
    # os.makedirs(f"output/hashes-v1/conda-packages/{subdir}/{letter}", exist_ok=True)

    # with open(f"output/hashes-v1/conda-packages/{subdir}/{letter}/{MAPPING}", mode="w") as mapping_file:
    #     json.dump(existing_mapping_data, mapping_file)

    # for file_sha in names_mapping:
    #     with open(f"output/hashes-v0/{file_sha}", mode="w") as file_dump:
    #         json.dump(names_mapping[file_sha], file_dump)
