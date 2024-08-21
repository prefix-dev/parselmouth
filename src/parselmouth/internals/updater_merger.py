import json
import os
import logging

from parselmouth.internals.s3 import s3_client


def main(output_dir: str):
    existing_mapping_data = s3_client.get_mapping()

    total_new_files = 0

    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        with open(filepath) as partial_file:
            partial_json = json.load(partial_file)
            existing_mapping_data.update(partial_json)
            total_new_files += 1

    logging.info(f"Total new files {total_new_files}")

    s3_client.upload_mapping(existing_mapping_data, "index.json")
