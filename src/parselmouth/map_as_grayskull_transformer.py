import json
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

account_id = os.environ["R2_PREFIX_ACCOUNT_ID"]
access_key_id = os.environ["R2_PREFIX_ACCESS_KEY_ID"]
access_key_secret = os.environ["R2_PREFIX_SECRET_ACCESS_KEY"]
bucket_name = os.environ["R2_PREFIX_BUCKET"]


def transform_mapping_in_grayskull_format(
    existing_mapping: dict, with_analytics: bool = False
):
    smaller_mapping: dict = {}

    different_mapping = []
    different_names = []
    multiple_names = []
    no_names = []

    existing_mapping = dict(
        sorted(existing_mapping.items(), key=lambda t: t[1]["package_name"])
    )

    for _cas_hash, mapping in existing_mapping_data.items():
        conda_name = mapping["conda_name"]

        pypi_name = mapping["pypi_normalized_names"]

        if conda_name in smaller_mapping:
            existing_pypi = smaller_mapping[conda_name]["pypi_name"]

            if existing_pypi != pypi_name:
                # sometimes mapping don't have path
                # a good example is
                # aesara-2.0.0-py36hb100763_0.tar.bz2 will have paths
                # and aesara-2.7.4-py310hd84b9e8_1.tar.bz2 will not
                previous_mapping = smaller_mapping[conda_name]["mapping"]
                different_mapping.append(
                    {"new_mapping": mapping, "previous_mapping": previous_mapping}
                )

                if pypi_name:
                    # sometimes and older version of package has a broken path to dist_info or egg_info
                    # here we overwrite the newer one with that old and broken
                    smaller_mapping[conda_name] = {
                        "mapping": mapping,
                        "pypi_name": pypi_name,
                    }
        else:
            if not pypi_name:
                # we don't write the mapping if pypi_name is not found
                # as we also have r-packages or cpp
                # so they don't belong in our map
                no_names.append(mapping)
                continue

            smaller_mapping[conda_name] = {"pypi_name": pypi_name, "mapping": mapping}

        if not pypi_name:
            no_names.append(mapping)
            continue

        if len(pypi_name) > 1:
            # some conda packages like stackvana-lsst_distrib-0.2024.13-py311hece06ba_0.conda
            # has different names
            # for this case I think it's better to not include this in mapping
            # as it is hard to guess what was the package to use it for
            multiple_names.append(mapping)
            continue

        first_one_name = pypi_name[0]

        if first_one_name != conda_name:
            # for statics purposes
            different_names.append(mapping)

    map_as_in_grayskull = {}

    # now le'ts iterate over created small_mapping
    # and format it for saving in json as grayskull one
    smaller_mapping = dict(sorted(smaller_mapping.items(), key=lambda t: t[0]))

    for conda_name, mapping in smaller_mapping.items():
        pypi_name = mapping["pypi_name"][0]

        map_as_in_grayskull[conda_name] = pypi_name

    with open("files/mapping_as_grayskull.json", "w") as map_file:
        json.dump(map_as_in_grayskull, map_file)

    if with_analytics:
        # I thinkg that is also good to have some analytics
        # about what we are collecting or transforming
        analytics_map = {
            "different_mapping": different_mapping,
            "different_names": different_names,
            "multiple_names": multiple_names,
            "no_names": no_names,
        }

        with open("analytics_map.json", "w") as anaylitcs_file:
            json.dump(analytics_map, anaylitcs_file)


if __name__ == "__main__":
    s3_client = boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=f"{access_key_id}",
        aws_secret_access_key=f"{access_key_secret}",
        region_name="eeur",  # Must be one of: wnam, enam, weur, eeur, apac, auto
    )

    obj_key = "hash-v0/index.json"
    response = s3_client.get_object(Bucket=bucket_name, Key=obj_key)
    existing_mapping_data: dict = json.loads(response["Body"].read().decode("utf-8"))
    transform_mapping_in_grayskull_format(existing_mapping_data)
