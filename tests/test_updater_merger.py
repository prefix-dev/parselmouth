import json
import os
from pathlib import Path
from conftests import MockS3
from parselmouth import updater_merger


def test_updater_merger_collects_all_packages_from_folder(tmp_path, capsys):
    test_s3_client = MockS3()

    updater_merger.s3_client = test_s3_client

    tmp_dir = tmp_path / "tmp_output"

    os.makedirs(tmp_dir)

    # make two files
    tmp_foo: Path = tmp_dir / "linux64@a.json"
    tmp_foo.touch()
    tmp_foo.write_text(json.dumps({"foo": {"name": "foo"}}))

    tmp_bar: Path = tmp_dir / "linux64@b"
    tmp_bar.touch()
    tmp_bar.write_text(json.dumps({"bar": {"name": "bar"}}))

    updater_merger.main(output_dir=tmp_dir)

    mock_mapping = test_s3_client._uploaded_mapping

    assert "foo" in mock_mapping
    assert "bar" in mock_mapping
