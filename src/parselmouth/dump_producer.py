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



if __name__ == "__main__":

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

    letters = set()

    for pkg_hash in existing_mapping_data:
        letters.add(f"{pkg_hash[0]}{pkg_hash[1]}")

    print(json.dumps(list(letters)))
    