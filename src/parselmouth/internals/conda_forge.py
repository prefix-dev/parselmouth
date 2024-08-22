import requests
import logging
from conda_forge_metadata.artifact_info.info_json import get_artifact_info_as_json
from urllib.parse import urljoin

from parselmouth.internals.channels import ChannelUrls, SupportedChannels


def get_all_archs_available(channel: SupportedChannels) -> list[str]:
    channel_url = ChannelUrls.main_channel(channel)

    response = requests.get(urljoin(channel_url, "channeldata.json"))
    channel_json = response.json()
    # Collect all subdirectories
    subdirs: list[str] = []
    for package in channel_json["packages"].values():
        subdirs.extend(package.get("subdirs", []))

    return list(set(subdirs))


def get_subdir_repodata(
    subdir: str, channel: SupportedChannels = SupportedChannels.CONDA_FORGE
) -> dict:
    channel_url = ChannelUrls.main_channel(channel)

    subdir_repodata = urljoin(channel_url, f"{subdir}/repodata.json")
    response = requests.get(subdir_repodata)
    if not response.ok:
        logging.error(
            f"Request for repodata to {subdir_repodata} failed. {response.reason}"
        )

    response.raise_for_status()

    return response.json()


def get_all_packages_by_subdir(
    subdir: str, channel: SupportedChannels = SupportedChannels.CONDA_FORGE
) -> dict[str, dict]:
    repodatas: dict[str, dict] = {}

    repodata = get_subdir_repodata(subdir, channel)

    repodatas.update(repodata["packages"])
    repodatas.update(repodata["packages.conda"])

    return repodatas


def get_artifact_info(
    subdir,
    artifact,
    backend,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
):
    return get_artifact_info_as_json(channel, subdir, artifact, backend)
