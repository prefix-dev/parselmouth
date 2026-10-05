import logging
import os
from datetime import datetime, timezone
from typing import Any

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import S3, s3_client

STATUS_SCHEMA_VERSION = 1


def build_status(
    channel: SupportedChannels,
    updated: bool,
    previous: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Build the status document.

    - `last_checked_at`: the last time a full updater run finished successfully
      (even if there was nothing new). This is the heartbeat.
    - `last_updated_at`: the last time new data was actually published. Carried over
      from the previous status unless this run published something.
    """
    now_iso = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    previous = previous or {}

    last_updated_at = now_iso if updated else previous.get("last_updated_at")

    status: dict[str, Any] = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "channel": str(channel),
        "last_checked_at": now_iso,
        "last_updated_at": last_updated_at,
    }

    run_id = os.getenv("GITHUB_RUN_ID")
    repository = os.getenv("GITHUB_REPOSITORY")
    if run_id and repository:
        server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
        status["run_url"] = f"{server}/{repository}/actions/runs/{run_id}"

    return status


def main(
    channel: SupportedChannels,
    updated: bool,
    upload: bool,
    s3: S3 | None = None,
) -> dict[str, Any]:
    s3_instance = s3 or s3_client

    previous = s3_instance.get_status(channel) if upload else None
    status = build_status(channel, updated, previous)
    logging.info(f"Status for {channel}: {status}")

    if upload:
        s3_instance.upload_status(status, channel)
    else:
        logging.info("Uploading is disabled. Skipping it.")

    return status
