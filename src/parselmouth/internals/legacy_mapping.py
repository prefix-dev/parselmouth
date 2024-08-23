import json
from deprecated import deprecated

from pydantic import BaseModel
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping, s3_client


class SmallMapping(BaseModel):
    pypi_name: list[str]


class CompressedMapping(BaseModel):
    pypi_name: list[str] | None


def format_and_save_mapping(
    mapping: dict[str, SmallMapping] | dict[str, CompressedMapping],
    mapping_name: str = "mapping_as_grayskull",
):
    # now le'ts iterate over created small_mapping
    # and format it for saving in json
    # where conda_name: pypi_name

    map_to_save = {}

    mapping = dict(sorted(mapping.items(), key=lambda t: t[0]))

    for conda_name, mapping_value in mapping.items():
        pypi_names = mapping_value.pypi_name
        pypi_name = pypi_names[0] if pypi_names else None

        map_to_save[conda_name] = pypi_name

    with open(f"files/{mapping_name}.json", "w") as map_file:
        json.dump(map_to_save, map_file)


def transform_mapping_in_grayskull_format(existing_mapping: IndexMapping):
    smaller_mapping: dict[str, SmallMapping] = {}

    compressed_mapping: dict[str, CompressedMapping] = {}

    existing_mapping.root = dict(
        sorted(existing_mapping.root.items(), key=lambda t: t[1].package_name)
    )

    for _cas_hash, mapping in existing_mapping.root.items():
        conda_name = mapping.conda_name

        pypi_name = mapping.pypi_normalized_names

        if conda_name in smaller_mapping:
            existing_pypi = smaller_mapping[conda_name].pypi_name

            if existing_pypi != pypi_name:
                # sometimes mapping don't have path
                # a good example is
                # aesara-2.0.0-py36hb100763_0.tar.bz2 will have paths
                # and aesara-2.7.4-py310hd84b9e8_1.tar.bz2 will not

                if pypi_name:
                    # sometimes and older version of package has a broken path to dist_info or egg_info
                    # here we overwrite the newer one with that old and broken
                    smaller_mapping[conda_name] = SmallMapping.model_validate(
                        {
                            "pypi_name": pypi_name,
                        }
                    )
                    compressed_mapping[conda_name] = CompressedMapping.model_validate(
                        {"pypi_name": pypi_name}
                    )

        else:
            if pypi_name:
                smaller_mapping[conda_name] = SmallMapping.model_validate(
                    {
                        "pypi_name": pypi_name,
                    }
                )

            # previously we didn't recorded packages that didn't have pypi name
            # now we will have a None pointing to conda name
            # to differentiate if we saw this package or not
            compressed_mapping[conda_name] = CompressedMapping.model_validate(
                {"pypi_name": pypi_name}
            )

    format_and_save_mapping(smaller_mapping)
    format_and_save_mapping(compressed_mapping, "compressed_mapping")


@deprecated(
    reason="This function is legacy and should not be used. Please use the one from mapping_transformer.py"
)
def main():
    existing_mapping_data = s3_client.get_channel_index(
        channel=SupportedChannels.CONDA_FORGE
    )
    if not existing_mapping_data:
        raise ValueError(
            f"Could not find the index data for channel {SupportedChannels.CONDA_FORGE}"
        )
    transform_mapping_in_grayskull_format(existing_mapping_data)
