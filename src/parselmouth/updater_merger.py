import io
import json
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

account_id = os.environ['R2_PREFIX_ACCOUNT_ID']
access_key_id = os.environ['R2_PREFIX_ACCESS_KEY_ID']
access_key_secret = os.environ['R2_PREFIX_SECRET_ACCESS_KEY']
bucket_name = os.environ['R2_PREFIX_BUCKET']



def upload(file_name: str, bucket_name: str, file_body: dict, s3_client):
    output = json.dumps(file_body)
    output_as_file = io.BytesIO(output.encode('utf-8'))
    
    s3_client.upload_fileobj(output_as_file, bucket_name, f"hash-v0/{file_name}")


if __name__ == "__main__":
    s3_client = boto3.client(
        service_name ="s3",
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id = f"{access_key_id}",
        aws_secret_access_key = f"{access_key_secret}",
        region_name="eeur", # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    obj_key = f"hash-v0/index.json"
    response = s3_client.get_object(Bucket=bucket_name, Key=obj_key)
    existing_mapping_data: dict = json.loads(response['Body'].read().decode('utf-8'))


    total_new_files = 0

    for filename in os.listdir('output'):
        filepath = os.path.join('output', filename)
        with open(filepath) as partial_file:
            partial_json = json.load(partial_file)
            existing_mapping_data.update(partial_json)
            total_new_files += 1


    print(f"Total new files {total_new_files}")

    # upload("index.json", bucket_name, existing_mapping_data, s3_client)




