import json
import os
import logging
from pathlib import Path

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping, s3_client


def main(output_dir: str, channel: SupportedChannels, upload: bool):
    existing_mapping_data = s3_client.get_channel_index(channel=channel)
    if not existing_mapping_data:
        existing_mapping_data = IndexMapping(root={})

    total_new_files = 0

    output_dir_location = Path(output_dir) / channel

    for filename in os.listdir(output_dir_location):
        with open(output_dir_location / filename) as partial_file:
            partial_json = json.load(partial_file)
            existing_mapping_data.root.update(partial_json)
            total_new_files += 1

    logging.info(f"Total new files {total_new_files}")

    if upload:
        logging.info("Uploading index to S3")
        s3_client.upload_index(existing_mapping_data, channel=channel)
    else:
        logging.info("Uploading is disabled. Skipping it.")
