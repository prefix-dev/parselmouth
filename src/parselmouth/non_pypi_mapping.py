import json
import boto3
import os
import logging
from dotenv import load_dotenv
import requests
import concurrent.futures
from requests.adapters import HTTPAdapter, Retry

from parselmouth.updater import get_all_archs_available, get_subdir_repodata

load_dotenv()

account_id = os.environ["R2_PREFIX_ACCOUNT_ID"]
access_key_id = os.environ["R2_PREFIX_ACCESS_KEY_ID"]
access_key_secret = os.environ["R2_PREFIX_SECRET_ACCESS_KEY"]
bucket_name = os.environ["R2_PREFIX_BUCKET"]

PYPI_API = "https://pypi.org/pypi/{package_name}/json"

requests_session = requests.Session()

retries = Retry(
    total=5,
    backoff_factor=0.1,  # type: ignore
)

requests_session.mount("https://", HTTPAdapter(max_retries=retries))


if __name__ == "__main__":
    s3_client = boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=f"{access_key_id}",
        aws_secret_access_key=f"{access_key_secret}",
        region_name="eeur",  # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    obj_key = "hash-v0/index.json"
    response = s3_client.get_object(Bucket=bucket_name, Key=obj_key)
    existing_mapping_data: dict = json.loads(response["Body"].read().decode("utf-8"))

    subdirs = get_all_archs_available()

    probably_non_pypi_packages: list[dict[str, dict]] = []

    for subdir in subdirs:
        repodatas = {}
        repodata = get_subdir_repodata(subdir)

        repodatas.update(repodata["packages"])
        repodatas.update(repodata["packages.conda"])

        for idx, package_name in enumerate(repodatas):
            package = repodatas[package_name]
            sha256 = package["sha256"]

            if sha256 not in existing_mapping_data:
                probably_non_pypi_packages.append(
                    {
                        "name": package["name"],
                        "package": package,
                        "filename": package_name,
                    }
                )
            elif not existing_mapping_data[sha256]["pypi_normalized_names"]:
                probably_non_pypi_packages.append(
                    {
                        "name": package["name"],
                        "package": package,
                        "filename": package_name,
                    }
                )

    all_probably_non_pypi_packages_unique_names = list(
        set([package["name"] for package in probably_non_pypi_packages])
    )

    not_existing_pypi_packages = []

    different_named_packages = []

    url_to_request = [
        (PYPI_API.format(package_name=name), name)
        for name in all_probably_non_pypi_packages_unique_names
    ]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                requests_session.get,
                url=package_url,
            ): package
            for package_url, package in url_to_request
        }

        for request_executed in concurrent.futures.as_completed(futures):
            package_name = futures[request_executed]
            # package_name = package['name']
            # package_hash = package["package"]["sha256"]
            # filename = package["filename"]

            try:
                response = request_executed.result()
            except Exception as e:
                logging.error(f"could not request {package_name}. Reason: {e}")

            if response.ok:
                logging.error(
                    f"{package_name} with {package_name} is present on pypi but missing in index.json mapping"
                )
                different_named_packages.append(package_name)

            elif response.status_code == 404:
                not_existing_pypi_packages.append(package_name)
            else:
                try:
                    response.raise_for_status()
                except requests.HTTPError as http_e:
                    logging.error(f"Could not request {response.url}. Reason: {http_e}")

    non_pypi_names = list(set([non_pypi for non_pypi in different_named_packages]))

    compressed_mapping = requests_session.get(
        "https://raw.githubusercontent.com/prefix-dev/parselmouth/main/files/mapping_as_grayskull.json"
    ).json()

    filtered_non_pypi_names = {}

    non_existing_pypi_packages = {}

    mapped_pypi_name_to_conda = {
        compressed_mapping[conda_key]: conda_key for conda_key in compressed_mapping
    }

    for non_pypi in non_pypi_names:
        if non_pypi in compressed_mapping:
            # sometimes  one of the version is missed by get_artifact_info 
            # for unknown reason
            # but it is a mapped package so we skip it
            continue
        filtered_non_pypi_names[non_pypi] = mapped_pypi_name_to_conda.get(
            non_pypi, None
        )

    with open("files/non_pypi_names.json", "w") as ff:
        json.dump(filtered_non_pypi_names, ff)

    for non_existing in not_existing_pypi_packages:
        if non_existing in mapped_pypi_name_to_conda:
            # some of the mapped pypi packages can come direct from 
            # gh releases without having a pypi alternative
            # so we track them in separate file for now
            non_existing_pypi_packages[non_existing] = mapped_pypi_name_to_conda.get(
                non_existing, None
            )

    with open("files/non_existing_pypi_packages.json", "w") as ff:
        json.dump(non_existing_pypi_packages, ff)
