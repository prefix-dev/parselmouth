import os
import logging
from pathlib import Path

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping, MappingEntry, s3_client


def main(output_dir: str, channel: SupportedChannels, upload: bool):
    existing_mapping_data = s3_client.get_channel_index(channel=channel)
    if not existing_mapping_data:
        existing_mapping_data = IndexMapping(root={})

    total_new_files = 0

    output_dir_location = Path(output_dir) / channel

    for filename in os.listdir(output_dir_location):
        partial_file = Path(output_dir) / filename

        mapping_entry = MappingEntry.model_validate_json(partial_file.read_text())
        existing_mapping_data.root.update(mapping_entry)
        total_new_files += 1

    logging.info(f"Total new files {total_new_files}")

    if upload:
        logging.info("Uploading index to S3")
        s3_client.upload_index(existing_mapping_data, channel=channel)
    else:
        logging.info("Uploading is disabled. Skipping it.")
