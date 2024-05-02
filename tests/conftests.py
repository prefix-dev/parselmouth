from parselmouth.s3 import S3


class MockS3(S3):
    _uploaded_mapping: dict

    def __init__(self) -> None:
        self._uploaded_mapping = {"012345as2": {"name": "a_name"}}

    def get_mapping(self) -> dict:
        return self._uploaded_mapping

    def upload_mapping(self, file_body: dict, file_name: str):
        self._uploaded_mapping[file_name] = file_body
