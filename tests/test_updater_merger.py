import json
import os
from pathlib import Path
from conftests import MockS3
from parselmouth.internals import updater_merger
from parselmouth.internals.channels import SupportedChannels


def test_updater_merger_collects_all_packages_from_folder(tmp_path, capsys):
    test_s3_client = MockS3()

    updater_merger.s3_client = test_s3_client

    tmp_dir = tmp_path / "tmp_output"

    os.makedirs(tmp_dir)

    os.makedirs(tmp_dir / "conda-forge")

    # make two files
    tmp_foo: Path = tmp_dir / "conda-forge" / "linux64@f.json"
    tmp_foo.touch()
    tmp_foo.write_text(
        json.dumps(
            {
                "foo": {
                    "pypi_normalized_names": ["foo"],
                    "versions": {"foo": "1.0.0"},
                    "conda_name": "foo",
                    "package_name": "foo",
                    "direct_url": ["https://foo.com"],
                }
            }
        )
    )

    tmp_bar: Path = tmp_dir / "conda-forge" / "linux64@b"
    tmp_bar.touch()
    tmp_bar.write_text(
        json.dumps(
            {
                "bar": {
                    "pypi_normalized_names": ["bar"],
                    "versions": {"bar": "1.0.0"},
                    "conda_name": "bar",
                    "package_name": "bar",
                    "direct_url": ["https://bar.com"],
                }
            }
        )
    )

    updater_merger.main(
        output_dir=tmp_dir, channel=SupportedChannels.CONDA_FORGE, upload=True
    )

    mock_index = test_s3_client._uploaded_index

    assert "foo" in mock_index.root
    assert "bar" in mock_index.root
