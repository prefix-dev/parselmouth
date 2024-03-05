import requests
import json

def get_subdir_repodata(subdir: str) -> dict:
    url = f"https://conda.anaconda.org/conda-forge/{subdir}/repodata.json"
    response = requests.get(url)
    if response.ok:
        return response.json()


def get_all_archs_available() -> set[str]:
    response = requests.get("https://conda.anaconda.org/conda-forge/channeldata.json")
    channel_json = response.json()
    # Collect all subdirectories
    # subdirs = "linux-64"
    
    subdirs: list[str] = ["osx-arm64"]
    # subdirs = []

    subdirs_with_letters = set()

    for subdir in subdirs:
        repodata = get_subdir_repodata(subdir)

        for package_name in repodata["packages.conda"]:
            first_letter = package_name[0]
            subdirs_with_letters.add(f"{subdir}@{first_letter}")



    return list(subdirs_with_letters)


if __name__ == "__main__":
    print(json.dumps(get_all_archs_available()))
