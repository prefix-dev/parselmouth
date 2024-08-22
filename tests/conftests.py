from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.conda_forge import get_subdir_repodata
from parselmouth.internals.s3 import S3, IndexMapping, MappingEntry


class MockS3(S3):
    _uploaded_index: IndexMapping
    _uploaded_mapping: list[tuple[str, MappingEntry]]

    def __init__(self) -> None:
        self._uploaded_index = IndexMapping.model_validate(
            {
                "012345as2": {
                    "pypi_normalized_names": ["a_name"],
                    "versions": {"a_name": "1.0.0"},
                    "conda_name": "a_name",
                    "package_name": "a_name",
                    "direct_url": ["https://a_url.com"],
                }
            }
        )
        self._uploaded_mapping = []

    def get_channel_index(self, channel: SupportedChannels) -> IndexMapping:
        return self._uploaded_index

    def upload_mapping(self, entry: MappingEntry, file_name: str):
        self._uploaded_mapping.append((file_name, entry))

    def upload_index(self, entry: IndexMapping, channel: SupportedChannels):
        self._uploaded_index.root.update(entry.root)


def mocked_get_all_packages_by_subdir(
    subdir: str, channel: SupportedChannels
) -> dict[str, dict]:
    repodatas: dict[str, dict] = {}

    repodata = get_subdir_repodata(subdir, channel)

    repodatas.update(repodata["packages"])
    repodatas.update(repodata["packages.conda"])

    small_repodatas = {}

    for idx, pkg_name in enumerate(repodatas):
        if "pymongo" in pkg_name:
            small_repodatas[pkg_name] = repodatas[pkg_name]

    return small_repodatas
