import io
import json
import logging
import os
from typing import Any, Optional, Annotated
from dotenv import load_dotenv
import boto3
import boto3.exceptions
from botocore.config import Config


from pydantic import BaseModel, RootModel

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.types import (
    PyPIName,
    PyPISourceUrl,
    PyPIVersion,
    CondaFileName,
    CondaPackageName,
)

CURRENT_VERSION = "v0"
RELATIONS_VERSION = "v1"

# Name of the main index file
INDEX_FILE = "index.json"

# Relations table files
RELATIONS_TABLE_FILE = "relations.jsonl.gz"
RELATIONS_METADATA_FILE = "metadata.json"
PYPI_TO_CONDA = "pypi-to-conda"


class MappingEntry(BaseModel):
    """
    Mapping entry that corresponds to a single conda file hash:
    conda_hash -> MappingEntry
    """

    # List of normalized names
    pypi_normalized_names: list[PyPIName] | None = None
    # List of versions, there will normally be a unique version for each name
    versions: dict[PyPIName, PyPIVersion] | None = None
    # Name of the package on conda
    conda_name: CondaPackageName
    # Name of the file on conda
    # todo: we should change this to FileName
    package_name: CondaFileName
    # List of direct urls to the package
    # these are used when the package is not on a PyPI index
    direct_url: list[PyPISourceUrl] | None = None


type CondaFileHash = Annotated[str, "Sha256 of the conda package"]


class IndexMapping(RootModel):
    """
    The index mapping is a mapping of hashes to `MappingEntry`
    """

    root: dict[CondaFileName, MappingEntry]


class S3:
    """
    This class is responsible for uploading and downloading files from S3.
    It's used to upload the index mapping and the mapping between PyPI and Conda and vice versa.
    """

    def __init__(self, client=None, bucket_name: Optional[str] = None) -> None:
        """
        Initialize S3 client.

        Args:
            client: Optional boto3 S3 client to use (for testing with moto)
            bucket_name: Optional bucket name override
        """
        if client is not None:
            # Use provided client (for testing)
            self._s3_client = client
            self.bucket_name = bucket_name or os.getenv("R2_PREFIX_BUCKET", "conda")
        else:
            # Create production client
            loaded = load_dotenv()
            if not loaded:
                logging.warning(
                    "no .env file was loaded. S3 requests may fail until R2_PREFIX_* keys are set."
                )

            account_id = os.getenv("R2_PREFIX_ACCOUNT_ID", "default")
            access_key_id = os.getenv("R2_PREFIX_ACCESS_KEY_ID", "")
            access_key_secret = os.getenv("R2_PREFIX_SECRET_ACCESS_KEY", "")
            self.bucket_name = bucket_name or os.getenv("R2_PREFIX_BUCKET", "conda")

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
        """
        Get the full index mapping for a channel, so this will contain all the hashes and their mapping entries.
        """
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
        """
        Upload a single mapping entry to S3.
        """
        output = entry.model_dump_json()
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file, self.bucket_name, f"hash-{CURRENT_VERSION}/{file_name}"
        )

    def upload_index(self, entry: IndexMapping, channel: SupportedChannels):
        output = entry.model_dump_json()
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file,
            self.bucket_name,
            f"hash-{CURRENT_VERSION}/{channel}/{INDEX_FILE}",
        )

    # ===== Relations Table Methods =====

    def upload_relations_table(
        self,
        table_data: bytes,
        channel: SupportedChannels,
    ) -> None:
        """
        Upload the master relations table (JSONL format, gzipped).

        This is the single source of truth for package relations.
        URL: /relations-{RELATIONS_VERSION}/{channel}/relations.jsonl.gz
        """
        key = f"relations-{RELATIONS_VERSION}/{channel}/{RELATIONS_TABLE_FILE}"
        logging.info(f"Uploading relations table to {key}")

        self._s3_client.upload_fileobj(
            io.BytesIO(table_data),
            self.bucket_name,
            key,
        )

    def upload_relations_metadata(
        self,
        metadata: dict[str, Any],
        channel: SupportedChannels,
    ) -> None:
        """
        Upload metadata about the relations table.

        URL: /relations-{RELATIONS_VERSION}/{channel}/metadata.json
        """
        key = f"relations-{RELATIONS_VERSION}/{channel}/{RELATIONS_METADATA_FILE}"
        logging.info(f"Uploading relations metadata to {key}")

        # Use json.dumps with default handler for datetime objects
        output = json.dumps(metadata, indent=2, default=str)
        self._s3_client.upload_fileobj(
            io.BytesIO(output.encode("utf-8")),
            self.bucket_name,
            key,
        )

    def upload_pypi_lookup_file(
        self,
        pypi_name: PyPIName,
        data: bytes,
        channel: SupportedChannels,
    ) -> None:
        """
        Upload a single PyPI -> Conda lookup file.

        These are derived from the relations table and cached for fast lookups.
        URL: /pypi-to-conda-{RELATIONS_VERSION}/{channel}/{pypi_name}.json
        """
        key = f"{PYPI_TO_CONDA}-{RELATIONS_VERSION}/{channel}/{pypi_name}.json"

        self._s3_client.upload_fileobj(
            io.BytesIO(data),
            self.bucket_name,
            key,
        )

    def get_pypi_lookup_file(
        self,
        pypi_name: PyPIName,
        channel: SupportedChannels,
    ) -> Optional[bytes]:
        """
        Download a single PyPI -> Conda lookup file.

        Returns:
            The JSON data as bytes, or None if not found
        """
        key = f"{PYPI_TO_CONDA}-{RELATIONS_VERSION}/{channel}/{pypi_name}.json"

        try:
            response = self._s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key,
            )
            return response["Body"].read()
        except self._s3_client.exceptions.NoSuchKey:
            return None

    def pypi_lookup_exists(
        self,
        pypi_name: PyPIName,
        channel: SupportedChannels,
    ) -> bool:
        """
        Check if a PyPI lookup file exists in S3.

        Returns:
            True if the file exists, False otherwise
        """
        key = f"{PYPI_TO_CONDA}-{RELATIONS_VERSION}/{channel}/{pypi_name}.json"

        try:
            self._s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key,
            )
            return True
        except self._s3_client.exceptions.NoSuchKey:
            return False
        except Exception:
            # For other errors, assume it doesn't exist
            return False

    def get_relations_table(
        self,
        channel: SupportedChannels,
    ) -> Optional[bytes]:
        """
        Download the master relations table.

        Returns:
            The compressed JSONL data, or None if not found
        """
        key = f"relations-{RELATIONS_VERSION}/{channel}/{RELATIONS_TABLE_FILE}"

        try:
            response = self._s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key,
            )
            return response["Body"].read()
        except self._s3_client.exceptions.NoSuchKey:
            logging.warning(f"Relations table not found: {key}")
            return None


s3_client = S3()
