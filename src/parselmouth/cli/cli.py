from typing import Annotated
import typer


from parselmouth.internals.updater_producer import main as updater_producer_main
from parselmouth.internals.updater import main as updater_main
from parselmouth.internals.check_one import main as check_one_main
from parselmouth.internals.updater_merger import main as update_merger_main
from parselmouth.internals.legacy_mapping import main as legacy_mapping_main
from parselmouth.internals.mapping_transformer import main as mapping_transformer_main

from parselmouth.internals.channels import SupportedChannels

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def main():
    """
    \bParselmouth is a tool used to generate a conda < -- > pypi mapping.
     It's functionality can be split up in three main parts:
    - `Updater producer` - this is the part that generates the subdir@letter list.
    - `Updater` - it's main responsibility is to use the subdir@letter list to generate the mapping.
    - `Updater merger` - it merges the partial mappings into a single mapping file which is later uploaded.
    """
    pass


@app.command()
def updater_producer(
    output_dir: str = "output_index",
    check_if_exists: bool = True,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
):
    """
    Generate the subdir@letter list.
    """

    updater_producer_main(
        output_dir=output_dir, check_if_exists=check_if_exists, channel=channel
    )


@app.command()
def updater(
    subdir_letter: Annotated[
        str,
        typer.Argument(
            help="Pass subdir@letter to get the new packages. Example: passing `noarch@s` will get all the packages from noarch subdir which start with `s` letter."
        ),
    ],
    output_dir: str = "output_index",
    partial_output_dir: str = "output",
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
):
    """
    Get all the packages based on subdir@letter and save it in partial_output_dir.
    To save requests to S3, we save our index in output_dir after running `updater-producer` command.

    Use `--upload` to enable uploading to S3. ( This is used in CI )

    """

    updater_main(
        subdir_letter=subdir_letter,
        output_dir=output_dir,
        partial_output_dir=partial_output_dir,
        channel=channel,
        upload=upload,
    )


@app.command()
def updater_merger(
    output_dir: str = "output",
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
):
    """
    This is used to merge all the partial mappings into a single mapping file during the CI run.

    """

    update_merger_main(output_dir, channel=channel, upload=upload)


@app.command()
def update_mapping_legacy():
    """
    This is used to update compressed files in the repository.
    """

    legacy_mapping_main()


@app.command()
def update_mapping():
    """
    This is used to update compressed files in the repository.
    """

    mapping_transformer_main()


@app.command()
def check_one(
    package_name: Annotated[
        str,
        typer.Argument(
            help="Pass full package name to get the mapping for it. Example: `warp-lang-1.3.0-cpu38_h19ae9ab_0.conda.`"
        ),
    ],
    subdir: Annotated[
        str,
        typer.Argument(help="Subdir for the package name"),
    ],
    backend: Annotated[
        str | None,
        typer.Option(
            help="What backend to use for the package. Supported backends: oci, libcfgraph, streamed."
        ),
    ] = None,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: Annotated[
        bool,
        typer.Option(help="Upload or overwrite already existing mapping."),
    ] = False,
):
    """
    Check mapping just for one package.
    You can also upload it to S3.
    """

    check_one_main(
        package_name=package_name, subdir=subdir, backend_type=backend, upload=upload
    )
