import requests
import logging
from conda_forge_metadata.artifact_info.info_json import get_artifact_info_as_json


def get_all_archs_available() -> list[str]:
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
    if not response.ok:
        logging.error(f"Request for repodata to {url} failed. {response.reason}")

    response.raise_for_status()

    return response.json()


def get_all_packages_by_subdir(subdir: str) -> dict[str, dict]:
    repodatas: dict[str, dict] = {}

    repodata = get_subdir_repodata(subdir)

    repodatas.update(repodata["packages"])
    repodatas.update(repodata["packages.conda"])

    return repodatas


def get_artifact_info(subdir, artifact, backend, channel="conda-forge"):
    return get_artifact_info_as_json(channel, subdir, artifact, backend)
