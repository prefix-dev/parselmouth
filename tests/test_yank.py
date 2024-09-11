from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.conda_forge import get_artifact_info
from parselmouth.internals.yank import YankConfig


def test_should_yank():
    """
    we know for sure that pyqt from osx-arm64 should be yanked
    so we test that the method should_yank returns True
    """
    package_name = "pyqt-5.15.7-py311h7203e35_3.conda"
    subdir = "osx-arm64"
    channel = SupportedChannels.CONDA_FORGE
    artifact_info = get_artifact_info(
        subdir=subdir,
        artifact=package_name,
        backend="streamed",
        channel=SupportedChannels.CONDA_FORGE,
    )
    assert artifact_info is not None

    yank_config = YankConfig.load_config()

    is_yanked = yank_config.should_yank(artifact_info, subdir, channel)

    assert is_yanked


def test_should_not_yank():
    """
    pyqt from linux-64 should *NOT* be yanked
    so we test that the method should_yank returns False
    """
    package_name = "pyqt-5.15.9-py310h04931ad_5.conda"
    subdir = "linux-64"
    channel = SupportedChannels.CONDA_FORGE
    artifact_info = get_artifact_info(
        subdir=subdir,
        artifact=package_name,
        backend="streamed",
        channel=SupportedChannels.CONDA_FORGE,
    )
    assert artifact_info is not None

    yank_config = YankConfig.load_config()

    is_yanked = yank_config.should_yank(artifact_info, subdir, channel)

    assert not is_yanked
