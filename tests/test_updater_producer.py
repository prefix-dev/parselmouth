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
        output_dir=tmp_dir,
        check_if_exists=True,
        check_if_pypi_exists=False,
        channel=SupportedChannels.CONDA_FORGE,
    )

    captured = capsys.readouterr()

    # serialize back letters
    letters_serialized = json.loads(captured.out)

    # the matrix must always fit into the GitHub Actions limit
    assert 0 < len(letters_serialized) <= updater_producer.MAX_MATRIX_JOBS

    # expand grouped entries (`subdir@a,b`) back into (subdir, letter) pairs
    covered = {
        (entry.split("@")[0], letter)
        for entry in letters_serialized
        for letter in entry.split("@")[1].split(",")
    }
    assert len(covered) >= 232
    assert ("noarch", "u") in covered

    mock_index = test_s3_client._uploaded_index

    index_json_path: Path = tmp_dir / "conda-forge" / "index.json"

    assert index_json_path.exists()

    content = IndexMapping.model_validate_json(index_json_path.read_text())
    assert content == mock_index


def test_build_matrix_keeps_single_letters_under_limit():
    letters_by_subdir = {"linux-64": {"b", "a"}, "noarch": {"c"}}

    matrix = updater_producer.build_matrix(letters_by_subdir, max_jobs=256)

    assert matrix == ["linux-64@a", "linux-64@b", "noarch@c"]


def test_build_matrix_groups_letters_when_over_limit():
    # 19 subdirs x 30 letters = 570 single-letter jobs, well above the limit
    letters = {chr(c) for c in range(ord("a"), ord("z") + 1)} | {"0", "1", "2", "_"}
    letters_by_subdir = {f"subdir-{i}": set(letters) for i in range(19)}

    matrix = updater_producer.build_matrix(letters_by_subdir, max_jobs=256)

    assert 0 < len(matrix) <= 256
    # every (subdir, letter) pair is still covered exactly once
    covered = set()
    for entry in matrix:
        subdir, group = entry.split("@")
        for letter in group.split(","):
            assert (subdir, letter) not in covered
            covered.add((subdir, letter))
    assert covered == {
        (subdir, letter) for subdir in letters_by_subdir for letter in letters
    }


def test_build_matrix_skips_empty_subdirs():
    assert updater_producer.build_matrix({"linux-64": set()}) == []
    assert updater_producer.build_matrix({}) == []
