import io
import json
import shutil
import sys
import os
import re
from typing import Optional
import requests
from conda_forge_metadata.artifact_info import get_artifact_info_as_json
import concurrent.futures
import logging
import boto3
from conda_oci_mirror.defaults import CACHE_DIR
from dotenv import load_dotenv


names_mapping: dict[str, str] = {}

dist_info_pattern = r"([^/]+)-(\d+[^/]*)\.dist-info\/METADATA"
egg_info_pattern = r"([^/]+?)-(\d+[^/]*)\.egg-info\/PKG-INFO"

dist_pattern_compiled = re.compile(dist_info_pattern)
egg_pattern_compiled = re.compile(egg_info_pattern)

# MAPPING = "mapping.json"

load_dotenv()

account_id = os.environ['R2_PREFIX_ACCOUNT_ID']
access_key_id = os.environ['R2_PREFIX_ACCESS_KEY_ID']
access_key_secret = os.environ['R2_PREFIX_SECRET_ACCESS_KEY']
bucket_name = os.environ['R2_PREFIX_BUCKET']


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

def upload(file_name: str, bucket_name: str, file_body: dict, s3_client):
    output = json.dumps(file_body)
    output_as_file = io.BytesIO(output.encode('utf-8'))
    
    s3_client.upload_fileobj(output_as_file, bucket_name, f"hash-v0/{file_name}")


if __name__ == "__main__":

    subdir, letter = sys.argv[1].split("@")
        
    all_packages: list[tuple[str, str]] = []


    s3_client = boto3.client(
        service_name ="s3",
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id = f"{access_key_id}",
        aws_secret_access_key = f"{access_key_secret}",
        region_name="eeur", # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    index_obj_key = "hash-v0/index.json"
    response = s3_client.get_object(Bucket=bucket_name, Key=index_obj_key)
    existing_mapping_data: dict = json.loads(response['Body'].read().decode('utf-8'))


    repodatas: dict[str, dict] = {}

    repodata = get_subdir_repodata(subdir)

    repodatas.update(repodata["packages"])
    repodatas.update(repodata["packages.conda"])
        
    for idx, package_name in enumerate(repodatas):
        if not package_name.startswith(letter):
            continue

        package = repodatas[package_name]
        sha256 = package["sha256"]

        if sha256 not in existing_mapping_data:
            all_packages.append(package_name)


    total = 0
    log_once = False
    logging.warning(f"Total packages for processing: {len(all_packages)} for {subdir}")


    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                get_artifact_info_as_json,
                channel="conda-forge",
                subdir=subdir,
                artifact=package_name,
                backend="streamed" if package_name.endswith('.conda') else "oci",
            ): package_name
            for package_name in all_packages
        }

        for done in concurrent.futures.as_completed(futures):
            total += 1
            if total % 1000 == 0:
                logging.warning(f"Done {total} from {len(all_packages)}")
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
    
    total = 0

    logging.warning(f'Starting to dump to S3 for {subdir}')

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                upload,
                file_name=package_hash,
                file_body=pkg_body,
                bucket_name=bucket_name,
                s3_client=s3_client,
            ): package_hash
            for package_hash, pkg_body in names_mapping.items()
        }

        for done in concurrent.futures.as_completed(futures):
            total += 1
            if total % 1000 == 0:
                logging.warning(f"Done {total} dumping to S3 from {len(names_mapping)}")
            pkg_hash = futures[done]
            try:
                done.result()
            except Exception as e:
                logging.error(f"could not upload it {pkg_hash} {e}")

    partial_json_name = f"{subdir}@{letter}.json"

    logging.warning(f"Producing partial index.json")

    
    os.makedirs(f"output", exist_ok=True)
    with open(f"output/{partial_json_name}", mode="w") as mapping_file:
        json.dump(names_mapping, mapping_file)


