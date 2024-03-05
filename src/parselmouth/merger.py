import io
import json
import boto3
import os
import concurrent.futures

import requests
import logging


account_id = os.environ['R2_ACCOUNT_ID']
access_key_id = os.environ['R2_ACCESS_KEY_ID']
access_key_secret = os.environ['R2_SECRET_ACCESS_KEY']
bucket_name = os.environ['R2_BUCKET']



def upload(package_hash: str, pkg_body: dict, s3_client):
    output = json.dumps(pkg_body)
    output_as_file = io.BytesIO(output.encode('utf-8'))
    
    s3_client.upload_fileobj(output_as_file, bucket_name, f"output/hashes-v1/{package_hash}")


if __name__ == "__main__":
    s3_client = boto3.client(
        service_name ="s3",
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id = f"{access_key_id}",
        aws_secret_access_key = f"{access_key_secret}",
        region_name="eeur", # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    response = requests.get("https://conda.anaconda.org/conda-forge/channeldata.json")
    channel_json = response.json()
    subdirs = []
    # Collect all subdirectories
    for package in channel_json["packages"].values():
        subdirs.extend(package.get("subdirs", []))

    for subdir_to_remove in ["linux-64", "win-64", "osx-64"]:
        subdirs.remove(subdir_to_remove)


    for subdir in subdirs:
        # Get object information
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=f'output/hashes-v1/{subdir}/mapping.json')

            data = response['Body'].read()
            mapping = json.loads(data)
        except Exception as e:
            logging.error(f"error while downloading mapping {subdir} {e}")
            continue
        
        logging.warning(f"Total: {len(mapping)} for {subdir}")
        
        total = 0

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    upload,
                    package_hash=package_hash,
                    pkg_body=pkg_body,
                    s3_client=s3_client,
                ): package_hash
                for package_hash, pkg_body in mapping.items()
            }

            for done in concurrent.futures.as_completed(futures):
                total += 1
                if total % 100000 == 0:
                    logging.warn(f"Done {total} from {len(mapping)}")
                pkg_hash = futures[done]
                try:
                    done.result()
                except Exception as e:
                    logging(f"could not upload it {pkg_hash} {e}")
