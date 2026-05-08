"""
One-shot invalidation of mapping records by conda package name.
"""

import asyncio
import logging
from typing import Optional

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.conda_forge import get_all_packages_by_subdir
from parselmouth.internals.remover import remove_from_s3
from parselmouth.internals.s3 import s3_client
from parselmouth.internals.subdirs import DEFAULT_SUBDIRS


def delete_main(
    names: list[str],
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    subdirs: Optional[list[str]] = None,
    dry_run: bool = True,
) -> None:
    """
    Delete existing mapping records for the given conda package `names` from
    R2 and drop them from the channel index, so the next updater run
    re-extracts them.
    """
    target_names = set(names)
    target_subdirs = subdirs if subdirs else DEFAULT_SUBDIRS

    existing_mapping_data = s3_client.get_channel_index(channel=channel)
    assert existing_mapping_data, f"No index found for channel {channel}"

    sha_to_remove: list[str] = []

    for subdir in target_subdirs:
        try:
            repodatas = get_all_packages_by_subdir(subdir, channel)
        except Exception as e:
            logging.warning(f"Could not fetch repodata for {subdir} on {channel}: {e}")
            continue

        for _label, packages in repodatas.items():
            for _filename, package in packages.items():
                if package.get("name") not in target_names:
                    continue
                sha256 = package.get("sha256")
                if not sha256:
                    continue
                if sha256 in existing_mapping_data.root:
                    sha_to_remove.append(sha256)

    logging.warning(
        f"Found {len(sha_to_remove)} mapping records to delete for "
        f"names={sorted(target_names)} on channel {channel}"
    )

    if dry_run:
        logging.warning("Dry-run: not deleting anything")
        return

    asyncio.run(remove_from_s3(sha_to_remove))

    for sha in sha_to_remove:
        existing_mapping_data.root.pop(sha, None)
    s3_client.upload_index(existing_mapping_data, channel=channel)

    logging.warning(
        f"Deleted {len(sha_to_remove)} records on {channel}; "
        "next updater run will re-extract them."
    )
