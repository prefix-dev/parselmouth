import asyncio
import io
import json
import os
from pathlib import Path
from typing import Optional
import aioboto3.session
import botocore.client
from conda_forge_metadata.types import ArtifactData
import concurrent.futures
import logging
from dotenv import load_dotenv

from parselmouth.internals.artifact import extract_artifact_mapping
from parselmouth.internals.channels import BackendRequestType, SupportedChannels
from parselmouth.internals.conda_forge import (
    get_all_packages_by_subdir,
    get_artifact_info,
)
from parselmouth.internals.s3 import IndexMapping

import aioboto3

from parselmouth.internals.yank import YankConfig


names_mapping: IndexMapping = IndexMapping.model_construct(root={})


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
    yank_config = YankConfig.load_config()

    subdir, letter = subdir_letter.split("@")

    all_packages: list[tuple[str, str]] = []

    index_location = Path(output_dir) / channel / "index.json"
    existing_mapping_data = IndexMapping.model_validate_json(index_location.read_text())

    repodatas_with_label = get_all_packages_by_subdir(subdir, channel)
    total_packages = set()

    for idx, (label, packages) in enumerate(repodatas_with_label.items()):
        for package_name in packages:
            if not package_name.startswith(letter):
                continue

            package = packages[package_name]
            # import pdb; pdb.set_trace()
            try:
                sha256 = package["sha256"]
            except Exception as e:
                import pdb; pdb.set_trace()
                print(e)
            if sha256 not in existing_mapping_data.root:
                # trying to get packages info using all backends.
                if (
                    package_name.endswith(".tar.bz2")
                    and channel == SupportedChannels.CONDA_FORGE
                ):
                    # Use OCI for conda-forge tar.bz2 as it is faster
                    all_packages.append((package_name, BackendRequestType.OCI))
                    total_packages.add(package_name)
                elif package_name.endswith(".tar.bz2") or package_name.endswith(
                    ".conda"
                ):
                    # Use streamed for other channels
                    if channel == SupportedChannels.TANGO_CONTROLS:
                        all_packages.append((package_name, BackendRequestType.DOWNLOAD))
                    else:
                        all_packages.append((package_name, BackendRequestType.STREAMED))
                    total_packages.add(package_name)
                else:
                    logging.warning(
                        f"Skipping {package_name} as it is not a .conda or .tar.bz2"
                    )

        total = 0
        logging.warning(
            f"Total packages for processing: {len(all_packages)} for {subdir}"
        )
        if channel == SupportedChannels.TANGO_CONTROLS:
            channel_to_request = (
                f"{SupportedChannels.TANGO_CONTROLS.value}/label/{label}"
            )
        else:
            channel_to_request = channel

        # import pdb; pdb.set_trace()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    get_artifact_info,
                    subdir=subdir,
                    artifact=package_name,
                    backend=backend_type,
                    channel=channel_to_request,
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
                        should_yank = yank_config.should_yank(artifact, subdir, channel)
                        if should_yank:
                            logging.info(
                                f"Skipping {package_name} from {subdir} {channel} as it should be yanked"
                            )
                            continue
                        sha = packages[package_name]["sha256"]
                        mapping_entry = extract_artifact_mapping(artifact, package_name)

                        # TODO: add an option to re-index only if the package don't have the normalized_names

                        names_mapping.root[sha] = mapping_entry
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
