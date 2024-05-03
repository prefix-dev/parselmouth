import json
from pathlib import Path
from conftests import MockS3
from parselmouth import updater_producer


def test_updater_producer_catch_new_packages(tmp_path, capsys):
    test_s3_client = MockS3()

    updater_producer.s3_client = test_s3_client

    tmp_dir = tmp_path / "tmp_output_index"
    updater_producer.main(output_dir=tmp_dir)

    captured = capsys.readouterr()

    # serialize back letters
    letters_serialized = json.loads(captured.out)

    assert len(letters_serialized) == 231

    mock_mapping = test_s3_client._uploaded_mapping

    index_json_path: Path = tmp_dir / "index.json"

    assert index_json_path.exists()

    content = json.loads(index_json_path.read_text())
    assert content == mock_mapping
