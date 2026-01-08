import asyncio
import io
import os
from typing import Optional
import aioboto3.session
import botocore.client
from conda_forge_metadata.types import ArtifactData
import concurrent.futures
import logging
from dotenv import load_dotenv
from parselmouth.internals.channels import BackendRequestType, SupportedChannels
from parselmouth.internals.conda_forge import (
    get_all_packages_by_subdir,
    get_artifact_info,
)
from parselmouth.internals.s3 import IndexMapping

import aioboto3

from parselmouth.internals.yank import YankConfig

from parselmouth.internals.s3 import s3_client


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


async def remove_from_s3(sha_to_remove: list[str]):
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
    async with session.client(  # type: ignore[call-overload]
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        config=config,
    ) as s3_client:
        tasks = [
            asyncio.ensure_future(
                s3_client.delete_object(Bucket=bucket_name, Key=f"hash-v0/{sha}")
            )
            for sha in sha_to_remove
        ]

        for task in asyncio.as_completed(tasks):
            await task
            total += 1

        logging.warning(f"Done {total} removing to S3 from {len(sha_to_remove)}")


def main(
    subdir: str,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    dry_run: bool = True,
):
    yank_config = YankConfig.load_config()

    all_packages: list[tuple[str, str]] = []

    existing_mapping_data = s3_client.get_channel_index(channel=channel)

    assert existing_mapping_data

    repodatas = get_all_packages_by_subdir(subdir, channel)

    for idx, package_name in enumerate(repodatas):
        package = repodatas[package_name]
        sha256 = package["sha256"]

        if sha256 in existing_mapping_data.root and any(
            name in package_name for name in yank_config.names
        ):
            # trying to get packages info using all backends.
            # note: streamed is not supported for .tar.gz
            all_packages.append((package_name, BackendRequestType.STREAMED))

    total = 0
    hash_to_remove = []
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
            package_name, _ = futures[done]
            try:
                artifact: Optional[ArtifactData] = done.result()
                if artifact:
                    should_yank = yank_config.should_yank(artifact, subdir, channel)
                    sha = repodatas[package_name]["sha256"]
                    if should_yank:
                        logging.info(
                            f"Adding {package_name} from {subdir} {channel} to remove list"
                        )
                        hash_to_remove.append(sha)

            except Exception as e:
                logging.error(f"An error occurred: {e} for package {package_name}")

    total = 0

    if not dry_run:
        logging.warning("Starting to removing hashes from S3")
        asyncio.run(remove_from_s3(hash_to_remove))

        # now remove from index file
        for sha in hash_to_remove:
            existing_mapping_data.root.pop(sha, None)
            total += 1

        s3_client.upload_index(existing_mapping_data, channel=channel)
    else:
        logging.warning(
            "Running in dry-run mode. This means that we do not actually remove"
        )

    logging.warning(
        f"Based on yank configuration we should remove : {len(hash_to_remove)}"
    )
