import json
import os
from pathlib import Path
from unittest.mock import patch
from parselmouth.internals import updater
from conftests import MockS3, mocked_get_all_packages_by_subdir
from parselmouth.internals.channels import SupportedChannels


@patch("parselmouth.internals.updater.upload_to_s3")
def test_updater(mocked_upload_to_s3, capsys, tmp_path):
    test_s3_client = MockS3()

    updater.get_all_packages_by_subdir = mocked_get_all_packages_by_subdir

    tmp_output_dir = tmp_path / "tmp_output_dir"
    tmp_partial_dir = tmp_path / "tmp_partial_dir"

    os.makedirs(tmp_output_dir)
    os.makedirs(tmp_output_dir / "conda-forge")
    index_json: Path = tmp_output_dir / "conda-forge" / "index.json"

    index_json.touch()
    index_json.write_text(json.dumps(test_s3_client._uploaded_index.model_dump()))

    updater.main(
        "linux-64@p",
        output_dir=tmp_output_dir,
        partial_output_dir=tmp_partial_dir,
        channel=SupportedChannels.CONDA_FORGE,
        upload=True,
    )

    # conda-forge never deletes packages
    # so we can assert based on some hashes

    pymongoarrow_hash = (
        "b8a2bac7385a33d13f51d7a92cd4dc47307ab0ac89218aae129c844d20324f76"
    )

    assert pymongoarrow_hash in mocked_upload_to_s3.call_args[0][0].root

    assert (tmp_partial_dir / "conda-forge" / "linux-64@p.json").exists()

    captured = capsys.readouterr()
    assert not captured.err
