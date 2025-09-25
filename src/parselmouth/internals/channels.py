from enum import StrEnum


Url = str


class BackendRequestType(StrEnum):
    OCI = "oci"
    STREAMED = "streamed"
    DOWNLOAD = "download"


class SupportedChannels(StrEnum):
    CONDA_FORGE = "conda-forge"
    PYTORCH = "pytorch"
    BIOCONDA = "bioconda"
    TANGO_CONTROLS = "tango-controls"

    @property
    def support_channeldata(self) -> bool:
        return self in {
            SupportedChannels.CONDA_FORGE,
            SupportedChannels.PYTORCH,
            SupportedChannels.BIOCONDA,
        }


class ChannelUrls:
    _ChannelUrls: dict[SupportedChannels, list[Url]] = {
        SupportedChannels.CONDA_FORGE: ["https://conda.anaconda.org/conda-forge/"],
        SupportedChannels.PYTORCH: ["https://conda.anaconda.org/pytorch/"],
        SupportedChannels.BIOCONDA: ["https://conda.anaconda.org/bioconda/"],
        SupportedChannels.TANGO_CONTROLS: [
            "https://conda.anaconda.org/tango-controls/"
        ],
    }

    @staticmethod
    def channels(channel: SupportedChannels) -> list[Url]:
        return ChannelUrls._ChannelUrls[channel]

    @staticmethod
    def main_channel(channel: SupportedChannels) -> Url:
        return ChannelUrls._ChannelUrls[channel][0]
