import json
from parselmouth.internals.s3 import s3_client


def format_and_save_mapping(mapping: dict, mapping_name: str = "mapping_as_grayskull"):
    # now le'ts iterate over created small_mapping
    # and format it for saving in json
    # where conda_name: pypi_name

    map_to_save = {}

    mapping = dict(sorted(mapping.items(), key=lambda t: t[0]))

    for conda_name, mapping in mapping.items():
        pypi_names = mapping["pypi_name"]
        pypi_name = pypi_names[0] if pypi_names else None

        map_to_save[conda_name] = pypi_name

    with open(f"files/{mapping_name}.json", "w") as map_file:
        json.dump(map_to_save, map_file)


def transform_mapping_in_grayskull_format(existing_mapping: dict):
    smaller_mapping: dict = {}

    compressed_mapping: dict = {}

    existing_mapping = dict(
        sorted(existing_mapping.items(), key=lambda t: t[1]["package_name"])
    )

    for _cas_hash, mapping in existing_mapping.items():
        conda_name = mapping["conda_name"]

        pypi_name = mapping["pypi_normalized_names"]

        if conda_name in smaller_mapping:
            existing_pypi = smaller_mapping[conda_name]["pypi_name"]

            if existing_pypi != pypi_name:
                # sometimes mapping don't have path
                # a good example is
                # aesara-2.0.0-py36hb100763_0.tar.bz2 will have paths
                # and aesara-2.7.4-py310hd84b9e8_1.tar.bz2 will not

                if pypi_name:
                    # sometimes and older version of package has a broken path to dist_info or egg_info
                    # here we overwrite the newer one with that old and broken
                    smaller_mapping[conda_name] = {
                        "pypi_name": pypi_name,
                    }
                    compressed_mapping[conda_name] = {"pypi_name": pypi_name}

        else:
            if pypi_name:
                smaller_mapping[conda_name] = {
                    "pypi_name": pypi_name,
                    "mapping": mapping,
                }

            # previously we didn't recorded packages that didn't have pypi name
            # now we will have a None pointing to conda name
            # to differentiate if we saw this package or not
            compressed_mapping[conda_name] = {"pypi_name": pypi_name}

    format_and_save_mapping(smaller_mapping)
    format_and_save_mapping(compressed_mapping, "compressed_mapping")


def main():
    existing_mapping_data = s3_client.get_mapping()
    transform_mapping_in_grayskull_format(existing_mapping_data)
