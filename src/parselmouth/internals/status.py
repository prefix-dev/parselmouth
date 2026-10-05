import logging
import os
from datetime import datetime, timezone
from typing import Any

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import S3, s3_client

STATUS_SCHEMA_VERSION = 2
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _to_unix(iso: str | None) -> int | None:
    if iso is None:
        return None
    return int(
        datetime.strptime(iso, ISO_FORMAT).replace(tzinfo=timezone.utc).timestamp()
    )


def build_status(
    channel: SupportedChannels,
    updated: bool,
    previous: dict[str, Any] | None,
    now: datetime | None = None,
    failed: bool = False,
) -> dict[str, Any]:
    """
    Build the status document.

    - `last_checked_at`: the last time a full updater run finished successfully
      (even if there was nothing new). This is the heartbeat.
    - `last_updated_at`: the last time new data was actually published. Carried over
      from the previous status unless this run published something.
    - `last_run_at` / `last_run_result`: the most recent run, successful or not.
    - `consecutive_failures`: failed runs since the last successful one.

    Every timestamp is also exposed as a `*_unix` integer, and `ok` as 1/0, for
    monitors that can only compare numbers (UptimeRobot, Prometheus json-exporter).
    """
    now_iso = (now or datetime.now(timezone.utc)).strftime(ISO_FORMAT)
    previous = previous or {}

    if failed:
        last_checked_at = previous.get("last_checked_at")
        last_updated_at = previous.get("last_updated_at")
        consecutive_failures = previous.get("consecutive_failures", 0) + 1
    else:
        last_checked_at = now_iso
        last_updated_at = now_iso if updated else previous.get("last_updated_at")
        consecutive_failures = 0

    status: dict[str, Any] = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "channel": str(channel),
        "ok": 0 if failed else 1,
        "last_run_result": "failure" if failed else "success",
        "consecutive_failures": consecutive_failures,
        "last_run_at": now_iso,
        "last_run_unix": _to_unix(now_iso),
        "last_checked_at": last_checked_at,
        "last_checked_unix": _to_unix(last_checked_at),
        "last_updated_at": last_updated_at,
        "last_updated_unix": _to_unix(last_updated_at),
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
    failed: bool = False,
) -> dict[str, Any]:
    s3_instance = s3 or s3_client

    previous = s3_instance.get_status(channel) if upload else None
    status = build_status(channel, updated, previous, failed=failed)
    logging.info(f"Status for {channel}: {status}")

    if upload:
        s3_instance.upload_status(status, channel)
    else:
        logging.info("Uploading is disabled. Skipping it.")

    return status
