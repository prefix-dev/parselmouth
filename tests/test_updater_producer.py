import json
from pathlib import Path
from conftests import MockS3
from parselmouth.internals import updater_producer
from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import IndexMapping


def test_updater_producer_catch_new_packages(tmp_path, capsys):
    test_s3_client = MockS3()

    updater_producer.s3_client = test_s3_client

    tmp_dir = tmp_path / "tmp_output_index"
    updater_producer.main(
        output_dir=tmp_dir, check_if_exists=True, channel=SupportedChannels.CONDA_FORGE
    )

    captured = capsys.readouterr()

    # serialize back letters
    letters_serialized = json.loads(captured.out)

    assert len(letters_serialized) >= 232
    assert "noarch@u" in letters_serialized

    mock_index = test_s3_client._uploaded_index

    index_json_path: Path = tmp_dir / "conda-forge" / "index.json"

    assert index_json_path.exists()

    content = IndexMapping.model_validate_json(index_json_path.read_text())
    assert content == mock_index
