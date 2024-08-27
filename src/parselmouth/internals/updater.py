import asyncio
import io
import json
import os
from pathlib import Path
import re
from typing import Optional
import aioboto3.session
import botocore.client
from conda_forge_metadata.types import ArtifactData
import concurrent.futures
import logging
from dotenv import load_dotenv
from packaging.version import parse
from parselmouth.internals.channels import BackendRequestType, SupportedChannels
from parselmouth.internals.conda_forge import (
    get_all_packages_by_subdir,
    get_artifact_info,
)
from parselmouth.internals.s3 import IndexMapping, MappingEntry
from parselmouth.internals.utils import normalize

import aioboto3


names_mapping: IndexMapping = IndexMapping.model_construct(root={})

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


async def async_upload_package(
    s3_client, pkg_body: str, package_hash, bucket_name: str
):
    try:
        # output = pkg_body.model_dump_json()
        output_as_file = io.BytesIO(pkg_body.encode("utf-8"))

        await s3_client.upload_fileobj(
            output_as_file, bucket_name, f"hash-v0/{package_hash}"
        )
    except Exception as e:
        logging.error(f"could not upload it {package_hash} {e}")


async def upload_to_s3(names_mapping: IndexMapping):
    total = 0
    load_dotenv()
    account_id = os.getenv("R2_PREFIX_ACCOUNT_ID", "default")
    access_key_id = os.getenv("R2_PREFIX_ACCESS_KEY_ID", "")
    access_key_secret = os.getenv("R2_PREFIX_SECRET_ACCESS_KEY", "")
    bucket_name = os.getenv("R2_PREFIX_BUCKET", "conda")

    session = aioboto3.Session(
        # service_name="s3",
        # endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=f"{access_key_id}",
        aws_secret_access_key=f"{access_key_secret}",
        region_name="eeur",  # Must be one of: wnam, enam, weur, eeur, apac, auto
    )
    config = botocore.client.Config(
        max_pool_connections=50,
    )
    async with session.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        config=config,
    ) as s3_client:
        tasks = [
            asyncio.ensure_future(
                async_upload_package(
                    s3_client, pkg_body.model_dump_json(), package_hash, bucket_name
                )
            )
            for package_hash, pkg_body in names_mapping.root.items()
        ]

        for task in asyncio.as_completed(tasks):
            await task
            total += 1
            if total % 1000 == 0:
                logging.warning(
                    f"Done {total} dumping to S3 from {len(names_mapping.root)}"
                )


def main(
    subdir_letter: str,
    output_dir: str = "output_index",
    partial_output_dir: str = "output",
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
):
    subdir, letter = subdir_letter.split("@")

    all_packages: list[tuple[str, str]] = []

    index_location = Path(output_dir) / channel / "index.json"
    existing_mapping_data = IndexMapping.model_validate_json(index_location.read_text())

    repodatas = get_all_packages_by_subdir(subdir, channel)
    total_packages = set()

    for idx, package_name in enumerate(repodatas):
        if not package_name.startswith(letter):
            continue

        package = repodatas[package_name]
        sha256 = package["sha256"]

        if sha256 not in existing_mapping_data:
            # trying to get packages info using all backends.
            # note: streamed is not supported for .tar.gz
            if package_name.endswith(".conda"):
                all_packages.append((package_name, BackendRequestType.STREAMED))
                total_packages.add(package_name)
            elif (
                package_name.endswith(".tar.bz2")
                and channel == SupportedChannels.CONDA_FORGE
            ):
                all_packages.append((package_name, BackendRequestType.OCI))
                total_packages.add(package_name)
            elif (
                package_name.endswith(".tar.bz2")
                and channel == SupportedChannels.PYTORCH
            ):
                all_packages.append((package_name, BackendRequestType.STREAMED))
                total_packages.add(package_name)
            else:
                logging.warning(
                    f"Skipping {package_name} as it is not a .conda or .tar.bz2"
                )

    total = 0
    logging.warning(f"Total packages for processing: {len(all_packages)} for {subdir}")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                get_artifact_info,
                subdir=subdir,
                artifact=package_name,
                backend=backend_type,
                channel=channel,
            ): (package_name, backend_type)
            for (package_name, backend_type) in all_packages
        }

        for done in concurrent.futures.as_completed(futures):
            total += 1
            if total % 1000 == 0:
                logging.warning(f"Done {total} from {len(all_packages)}")
            package_name, backend_type = futures[done]
            try:
                artifact: Optional[ArtifactData] = done.result()
                if artifact:
                    pypi_names_and_versions = get_pypi_names_and_version(
                        artifact["files"]
                    )
                    pypi_normalized_names = (
                        [name for name in pypi_names_and_versions]
                        if pypi_names_and_versions
                        else None
                    )
                    source: Optional[dict] = artifact["rendered_recipe"].get(
                        "source", None
                    )
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
                        direct_url = [str(url)] if isinstance(url, str) else url

                    if sha not in names_mapping:
                        names_mapping.root[sha] = MappingEntry.model_validate(
                            {
                                "pypi_normalized_names": pypi_normalized_names,
                                "versions": pypi_names_and_versions
                                if pypi_names_and_versions
                                else None,
                                "conda_name": str(conda_name),
                                "package_name": package_name,
                                "direct_url": direct_url,
                            }
                        )
                else:
                    logging.warning(
                        f"Could not get artifact for {package_name} using backend: {backend_type}"
                    )

            except Exception as e:
                logging.error(f"An error occurred: {e} for package {package_name}")

    total = 0

    if upload:
        logging.warning(f"Starting to dump to S3 for {subdir}")
        # using async approach over multithread is much more faster
        # same should be done for extracting the metadata
        asyncio.run(upload_to_s3(names_mapping))
    else:
        logging.warning(f"Uploading is disabled for {subdir}. Skipping it.")

    logging.warning(
        f"Processed {len(names_mapping.root)} packages out of {len(total_packages)}"
    )

    partial_json_name = f"{subdir}@{letter}.json"

    logging.warning("Producing partial index.json")

    partial_output_dir_location = Path(partial_output_dir) / channel
    os.makedirs(partial_output_dir_location, exist_ok=True)

    with open(
        partial_output_dir_location / partial_json_name, mode="w"
    ) as mapping_file:
        json.dump(names_mapping.model_dump(), mapping_file)
