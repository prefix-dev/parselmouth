import json
import os
from pathlib import Path
from parselmouth.internals import updater
from conftests import MockS3, mocked_get_all_packages_by_subdir


def test_updater(capsys, tmp_path):
    test_s3_client = MockS3()

    updater.s3_client = test_s3_client

    updater.get_all_packages_by_subdir = mocked_get_all_packages_by_subdir

    tmp_output_dir = tmp_path / "tmp_output_dir"
    tmp_partial_dir = tmp_path / "tmp_partial_dir"

    os.makedirs(tmp_output_dir)
    index_json: Path = tmp_output_dir / "index.json"

    index_json.touch()
    index_json.write_text(json.dumps(test_s3_client._uploaded_mapping))

    updater.main(
        "linux-64@p",
        output_dir=tmp_output_dir,
        partial_output_dir=tmp_partial_dir,
        upload=True,
    )

    # conda-forge never deletes packages
    # so we can assert based on some hashes
    uploaded_mapping = test_s3_client._uploaded_mapping

    pymongoarrow_hash = (
        "b8a2bac7385a33d13f51d7a92cd4dc47307ab0ac89218aae129c844d20324f76"
    )

    assert pymongoarrow_hash in uploaded_mapping

    assert (
        uploaded_mapping[pymongoarrow_hash]["pypi_normalized_names"][0]
        == "pymongoarrow"
    )
    assert (tmp_partial_dir / "linux-64@p.json").exists()

    captured = capsys.readouterr()
    assert not captured.err
