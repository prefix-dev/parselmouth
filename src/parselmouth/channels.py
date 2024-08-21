from enum import StrEnum


Url = str


class SupportedChannels(StrEnum):
    CONDA_FORGE = "conda-forge"
    PYTORCH = "pytorch"


class BackendRequestType(StrEnum):
    OCI = "oci"
    LIBCFGRAPH = "libcfgraph"
    STREAMED = "streamed"


class ChannelUrls:
    _ChannelUrls: dict[SupportedChannels, list[Url]] = {
        SupportedChannels.CONDA_FORGE: ["https://conda.anaconda.org/conda-forge/"],
        SupportedChannels.PYTORCH: ["https://conda.anaconda.org/pytorch/"],
    }

    @staticmethod
    def channels(channel: SupportedChannels) -> list[Url]:
        return ChannelUrls._ChannelUrls[channel]

    @staticmethod
    def main_channel(channel: SupportedChannels) -> Url:
        return ChannelUrls._ChannelUrls[channel][0]
