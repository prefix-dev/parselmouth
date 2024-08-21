from parselmouth.internals.conda_forge import get_subdir_repodata
from parselmouth.internals.s3 import S3


class MockS3(S3):
    _uploaded_mapping: dict

    def __init__(self) -> None:
        self._uploaded_mapping = {"012345as2": {"name": "a_name"}}

    def get_mapping(self) -> dict:
        return self._uploaded_mapping

    def upload_mapping(self, file_body: dict, file_name: str):
        self._uploaded_mapping[file_name] = file_body


def mocked_get_all_packages_by_subdir(subdir: str) -> dict[str, dict]:
    repodatas: dict[str, dict] = {}

    repodata = get_subdir_repodata(subdir)

    repodatas.update(repodata["packages"])
    repodatas.update(repodata["packages.conda"])

    small_repodatas = {}

    for idx, pkg_name in enumerate(repodatas):
        if "pymongo" in pkg_name:
            small_repodatas[pkg_name] = repodatas[pkg_name]

    return small_repodatas
