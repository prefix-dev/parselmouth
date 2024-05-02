import io
import json
import logging
import os
from dotenv import load_dotenv
import boto3

CURRENT_VERSION = "v0"
MAPPING_FILE = "index.json"


class S3:
    def __init__(self) -> None:
        loaded = load_dotenv()
        if not loaded:
            logging.warning(
                "no .env file was loaded. S3 requests may fail until R2_PREFIX_* keys are set."
            )
        else:
            logging.info("s3 client initialised")

        account_id = os.getenv("R2_PREFIX_ACCOUNT_ID", "some_id")
        access_key_id = os.getenv("R2_PREFIX_ACCESS_KEY_ID", "")
        access_key_secret = os.getenv("R2_PREFIX_SECRET_ACCESS_KEY", "")
        bucket_name = os.getenv("R2_PREFIX_BUCKET", "conda")

        self.bucket_name = bucket_name

        s3_client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=f"{access_key_id}",
            aws_secret_access_key=f"{access_key_secret}",
            region_name="eeur",  # Must be one of: wnam, enam, weur, eeur, apac, auto
        )
        self._s3_client = s3_client

    def get_mapping(self) -> dict:
        assert self._s3_client
        index_obj_key = f"hash-{CURRENT_VERSION}/{MAPPING_FILE}"
        response = self._s3_client.get_object(
            Bucket=self.bucket_name, Key=index_obj_key
        )
        return json.loads(response["Body"].read().decode("utf-8"))

    def upload_mapping(self, file_body: dict, file_name: str):
        output = json.dumps(file_body)
        output_as_file = io.BytesIO(output.encode("utf-8"))

        self._s3_client.upload_fileobj(
            output_as_file, self.bucket_name, f"hash-v0/{file_name}"
        )


s3_client = S3()
