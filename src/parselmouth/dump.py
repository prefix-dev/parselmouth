import io
import json
import sys
import boto3
import os
import re
import concurrent.futures

import requests
import logging


account_prefix_id = os.environ['R2_PREFIX_ACCOUNT_ID']
access_prefix_key_id = os.environ['R2_PREFIX_ACCESS_KEY_ID']
access_prefix_key_secret = os.environ['R2_PREFIX_SECRET_ACCESS_KEY']
prefix_bucket_name = os.environ['R2_PREFIX_BUCKET']


def upload(file_name: str, bucket_name: str, file_body: dict, s3_client):
    output = json.dumps(file_body)
    output_as_file = io.BytesIO(output.encode('utf-8'))
    
    s3_client.upload_fileobj(output_as_file, bucket_name, f"hash-v0/{file_name}")


if __name__ == "__main__":
    letter = sys.argv[1]

    s3_prefix_client = boto3.client(
        service_name ="s3",
        endpoint_url = f"https://{account_prefix_id}.r2.cloudflarestorage.com",
        aws_access_key_id = f"{access_prefix_key_id}",
        aws_secret_access_key = f"{access_prefix_key_secret}",
        region_name="eeur", # Must be one of: wnam, enam, weur, eeur, apac, auto
    )


    obj_key = f"hash-v0/index.json"
    response = s3_prefix_client.get_object(Bucket=prefix_bucket_name, Key=obj_key)
    existing_mapping_data = json.loads(response['Body'].read().decode('utf-8'))

    to_dump = {}

    for pkg_hash, pkg in existing_mapping_data.items():
        if pkg_hash.startswith(letter):
            to_dump[pkg_hash] = pkg

    total = 0

    logging.warning(f"Total {len(to_dump)}")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                upload,
                file_name=package_hash,
                file_body=pkg_body,
                bucket_name=prefix_bucket_name,
                s3_client=s3_prefix_client,
            ): package_hash
            for package_hash, pkg_body in to_dump.items()
        }

        for done in concurrent.futures.as_completed(futures):
            total += 1
            if total % 1000 == 0:
                logging.warning(f"Done {total} from {len(to_dump)}")
            pkg_hash = futures[done]
            try:
                done.result()
            except Exception as e:
                logging.error(f"could not upload it {pkg_hash} {e}")


    print('completed')