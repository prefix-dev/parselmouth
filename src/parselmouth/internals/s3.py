import io
import json
import logging
import os
from typing import Any, Optional
from dotenv import load_dotenv
import boto3
import boto3.exceptions
from botocore.config import Config


from pydantic import BaseModel, RootModel

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.schema import SchemaJsonEncoder

CURRENT_VERSION = "v0"

INDEX_FILE = "index.json"


PYPI_TO_CONDA = "pypi-to-conda"
PYPI_TO_CONDA_INDEX = "index"

SCHEMA = "schema"
SCHEMA_FILE = "schema.json"


class MappingEntry(BaseModel):
    pypi_normalized_names: list[str] | None = None
    versions: dict[str, str] | None = None
    conda_name: str
    package_name: str
    direct_url: list[str] | None = None


class IndexMapping(RootModel):
    root: dict[str, MappingEntry]


class S3:
    def __init__(self) -> None:
        loaded = load_dotenv()
        if not loaded:
            logging.warning(
                "no .env file was loaded. S3 requests may fail until R2_PREFIX_* keys are set."
            )

        account_id = os.getenv("R2_PREFIX_ACCOUNT_ID", "default")
        access_key_id = os.getenv("R2_PREFIX_ACCESS_KEY_ID", "")
        access_key_secret = os.getenv("R2_PREFIX_SECRET_ACCESS_KEY", "")
        bucket_name = os.getenv("R2_PREFIX_BUCKET", "conda")

        self.bucket_name = bucket_name

        boto_config = Config(
            max_pool_connections=50,
        )

        s3_client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=f"{access_key_id}",
            aws_secret_access_key=f"{access_key_secret}",
            region_name="eeur",  # Must be one of: wnam, enam, weur, eeur, apac, auto
            config=boto_config,
        )
        self._s3_client = s3_client

    def get_channel_index(self, channel: SupportedChannels) -> Optional[IndexMapping]:
        assert self._s3_client
        index_obj_key = f"hash-{CURRENT_VERSION}/{channel}/{INDEX_FILE}"
        try:
            response = self._s3_client.get_object(
                Bucket=self.bucket_name, Key=index_obj_key
            )
        except self._s3_client.exceptions.NoSuchKey:
            return None

        return IndexMapping.model_validate_json(response["Body"].read().decode("utf-8"))

    def upload_mapping(self, entry: MappingEntry, file_name: str):
        output = entry.model_dump_json()
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file, self.bucket_name, f"hash-{CURRENT_VERSION}/{file_name}"
        )

    def upload_pypi_mapping(
        self,
        entry: dict[str, list[str]],
        file_name: str,
        channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    ):
        file_name = f"{PYPI_TO_CONDA}-{CURRENT_VERSION}/{channel}/{file_name}.json"

        output = json.dumps(entry)
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file,
            self.bucket_name,
            f"{PYPI_TO_CONDA}-{CURRENT_VERSION}/{channel}/{file_name}.json",
        )

    def upload_pypi_mapping_index(
        self,
        entry: dict[str, dict[str, list[str]]],
        channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    ):
        output = json.dumps(entry)
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file,
            self.bucket_name,
            f"{PYPI_TO_CONDA}-{CURRENT_VERSION}/{channel}/{PYPI_TO_CONDA_INDEX}/{INDEX_FILE}",
        )

    def upload_pypi_mapping_schema(
        self,
        entry: dict[str, Any],
        channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    ):
        output = json.dumps(entry, cls=SchemaJsonEncoder)
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file,
            self.bucket_name,
            f"{PYPI_TO_CONDA}-{CURRENT_VERSION}/{channel}/{SCHEMA}/{SCHEMA_FILE}",
        )

    def upload_index(self, entry: IndexMapping, channel: SupportedChannels):
        output = entry.model_dump_json()
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file,
            self.bucket_name,
            f"hash-{CURRENT_VERSION}/{channel}/{INDEX_FILE}",
        )


s3_client = S3()
