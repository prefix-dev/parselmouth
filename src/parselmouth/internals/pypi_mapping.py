"""
This module is responsible to produce a
{
    pypi-name ->{ pypi_version: [
            (conda-name): PyPiEntry,
            ...
        ]
    ]
}

from already existing
{
    "hash": {
        ....
    }
}

"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, List, Optional
from tqdm import tqdm
from parselmouth.internals.types import PyPIName, PyPIVersion, CondaPackageName

from pydantic import Field, RootModel, StringConstraints
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping, MappingEntry, s3_client

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
VersionStr = NonEmptyStr
PyPIToCondaMappingUnique = dict[PyPIName, dict[PyPIVersion, set[CondaPackageName]]]
PyPIToCondaMapping = dict[PyPIName, dict[PyPIVersion, list[CondaPackageName]]]


class PyPiEntry(RootModel):
    root: dict[NonEmptyStr, List[NonEmptyStr]] = Field(
        description="A pypi entry that consist of the pypi version to the conda names"
    )


class PyPiToConda(RootModel):
    root: dict[NonEmptyStr, PyPiEntry] = Field(
        description="A mapping that consist of the pypi names to the `PyPiEntry`"
    )


def process_index_entry(
    entry: MappingEntry,
) -> Optional[PyPIToCondaMappingUnique]:
    """
    return a tuple of pypi_names to conda_names
    """
    records: PyPIToCondaMappingUnique = defaultdict(lambda: defaultdict(set))

    if not entry.pypi_normalized_names:
        return None

    for pypi_name in entry.pypi_normalized_names:
        if not entry.versions:
            return None

        records[pypi_name][entry.versions[pypi_name]].add(entry.conda_name)

    return records


def convert_mapping_to_inverse(index: IndexMapping) -> PyPIToCondaMappingUnique:
    """
    Create a mapping from the Conda -> PyPI mapping, but in reverse
    esentially creating the PyPI -> Conda mapping
    """
    # default dict
    pypi_name_to_conda_name: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set[str])
    )

    total = len(index.root)
    processed = 0
    for entry in index.root.values():
        print(f"Processing {processed} of {total}")
        processed += 1
        name_to_pypi_version_to_conda = process_index_entry(entry)
        if not name_to_pypi_version_to_conda:
            continue

        # update dict
        for pypi_name, pypi_version_to_conda in name_to_pypi_version_to_conda.items():
            for pypi_version, conda_name in pypi_version_to_conda.items():
                pypi_name_to_conda_name[pypi_name][pypi_version].update(conda_name)

    return pypi_name_to_conda_name


def generate_pypi_to_conda_schema() -> dict[str, Any]:
    """Returns the schema for the PyPi to Conda mapping as string"""
    return PyPiToConda.model_json_schema()


def main(channel: SupportedChannels):
    existing_mapping_data = s3_client.get_channel_index(channel=channel)
    if not existing_mapping_data:
        raise ValueError(f"Channel {channel} does not exist or is empty")

    pypi_name_to_conda_name_unique = convert_mapping_to_inverse(existing_mapping_data)

    # convert inside set to list
    pypi_name_to_conda_name: PyPIToCondaMapping = {
        k: {kk: list(vv) for kk, vv in v.items()}
        for k, v in pypi_name_to_conda_name_unique.items()
    }

    # upload mapping to s3
    # todo: this don't check if mapping already exists before uploading it
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                s3_client.upload_pypi_mapping, pypi_version_to_conda, pypi_name
            )
            for pypi_name, pypi_version_to_conda in tqdm(
                pypi_name_to_conda_name.items(), desc="Uploading files"
            )
        ]

        # Optional: wait for all uploads to complete and check for errors
        for future in tqdm(futures, desc="Finalizing uploads"):
            future.result()  # This will raise an exception if the upload fails

    # upload mapping index to s3
    s3_client.upload_pypi_mapping_index(pypi_name_to_conda_name)

    mapping_schema = generate_pypi_to_conda_schema()

    s3_client.upload_pypi_mapping_schema(mapping_schema)

    return pypi_name_to_conda_name


if __name__ == "__main__":
    main(SupportedChannels.CONDA_FORGE)
