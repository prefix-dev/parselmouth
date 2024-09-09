# this module is responsible for yanking some of the mapping files
# that are wrong in the feedstock for the specific packages subdirs.
# a good example is pyqt-5.15.7-py311h7203e35_3.conda from osx-arm64
# which do not contains .dist-info or .egg-info, but the conda package
# from pyqt-5.15.9-py310h04931ad_5.conda linux-64 does.
# We know that this is a pypi package, so as exception
# we maintain a list of this exceptions, and do not store hashes for them.
# this means that tools like pixi, could fallback to the compressed mapping
# and extract pyqt name for there.
from pathlib import Path
from pydantic import BaseModel
from conda_forge_metadata.types import ArtifactData

from ruamel.yaml import YAML

from parselmouth.internals.channels import SupportedChannels

DEFAULT_YANK_CONFIG = Path("yank.yaml")


class PackageInfo(BaseModel):
    name: str
    platforms: list[str]
    channels: list[SupportedChannels]


class YankConfig(BaseModel):
    packages: list[PackageInfo]

    @classmethod
    def load_config(cls, file_path: Path = DEFAULT_YANK_CONFIG) -> "YankConfig":
        with open(file_path, "r") as file:
            yaml_content = YAML(typ="safe", pure=True).load(file)
            return YankConfig(**yaml_content)

    def should_yank(
        self, artifact: ArtifactData, subdir: str, channel: SupportedChannels
    ) -> bool:
        for package in self.packages:
            if artifact["name"] == package.name:
                if subdir in package.platforms:
                    if channel in package.channels:
                        return True
        return False

    @property
    def names(self) -> list[str]:
        return [package.name for package in self.packages]
