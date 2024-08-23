import json
import os.path

from pydantic import BaseModel
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping, s3_client


FILES_DIR = "files"

FILES_VERSION = "v0"


class CompressedMapping(BaseModel):
    pypi_names: list[str] | None = None


def _format_and_save_mapping(
    compressed_mapping: dict[str, CompressedMapping],
    channel: SupportedChannels,
    mapping_name: str = "mapping",
):
    # now le'ts iterate over created small_mapping
    # and format it for saving in json
    # where conda_name: pypi_names
    map_to_save = {}

    compressed_mapping = dict(sorted(compressed_mapping.items(), key=lambda t: t[0]))

    for conda_name, mapping in compressed_mapping.items():
        pypi_names = mapping.pypi_names

        map_to_save[conda_name] = pypi_names

    os.makedirs(os.path.join(FILES_DIR, FILES_VERSION, channel), exist_ok=True)

    mapping_location = os.path.join(
        FILES_DIR, FILES_VERSION, channel, f"{mapping_name}.json"
    )

    with open(mapping_location, "w") as map_file:
        json.dump(map_to_save, map_file)


def transform_mapping_and_save(
    existing_mapping: IndexMapping, channel: SupportedChannels
):
    compressed_mapping: dict[str, CompressedMapping] = {}

    existing_mapping.root = dict(
        sorted(existing_mapping.root.items(), key=lambda t: t[1].package_name)
    )

    for _cas_hash, mapping in existing_mapping.root.items():
        conda_name = mapping.conda_name

        pypi_names = mapping.pypi_normalized_names

        if conda_name in compressed_mapping:
            existing_pypi = compressed_mapping[conda_name].pypi_names

            if existing_pypi != pypi_names:
                # sometimes mapping don't have path
                # a good example is
                # aesara-2.0.0-py36hb100763_0.tar.bz2 will have paths
                # and aesara-2.7.4-py310hd84b9e8_1.tar.bz2 will not

                if pypi_names:
                    # sometimes and older version of package has a broken path to dist_info or egg_info
                    # here we overwrite the newer one with that old and broken
                    compressed_mapping[conda_name] = CompressedMapping(
                        pypi_names=pypi_names
                    )

        else:
            # previously we didn't recorded packages that didn't have pypi name
            # now we will have a None pointing to conda name
            # to differentiate if we saw this package or not
            compressed_mapping[conda_name] = CompressedMapping(pypi_names=pypi_names)

    _format_and_save_mapping(compressed_mapping, channel, "compressed_mapping")


def main(channel: SupportedChannels = SupportedChannels.CONDA_FORGE):
    existing_mapping_data = s3_client.get_channel_index(channel=channel)
    if not existing_mapping_data:
        raise ValueError(f"Could not find the index data for channel {channel}")

    transform_mapping_and_save(existing_mapping_data, channel)
