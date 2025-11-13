from typing import Annotated, Optional
import typer


from parselmouth.internals.updater_producer import main as updater_producer_main
from parselmouth.internals.updater import main as updater_main
from parselmouth.internals.check_one import main as check_one_main
from parselmouth.internals.updater_merger import main as update_merger_main
from parselmouth.internals.legacy_mapping import main as legacy_mapping_main
from parselmouth.internals.mapping_transformer import main as mapping_transformer_main
from parselmouth.internals.relations_updater import main as relations_updater_main
from parselmouth.internals.remover import main as remover_main
from parselmouth.internals.package_explorer import explore_package

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
    check_if_pypi_exists: bool = False,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    subdir: Optional[str] = None,
):
    """
    Generate the subdir@letter list.
    """

    updater_producer_main(
        output_dir=output_dir,
        check_if_exists=check_if_exists,
        check_if_pypi_exists=check_if_pypi_exists,
        channel=channel,
        subdir=subdir,
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
def update_mapping(channel: SupportedChannels = SupportedChannels.CONDA_FORGE):
    """
    This is used to update compressed files in the repository.
    """

    mapping_transformer_main(channel=channel)


@app.command()
def update_relations_table(
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
    output_dir: Optional[str] = None,
    skip_unchanged: bool = True,
):
    """
    Generate and upload the package relations table (recommended approach).

    This creates:
    - Master relations table (JSONL) at /relations-v1/{channel}/relations.jsonl.gz
    - PyPI -> Conda lookup files at /pypi-to-conda-v1/{channel}/{pypi_name}.json

    The table-based approach is the single source of truth for package mappings.
    Both Conda->PyPI and PyPI->Conda lookups are derived from this table.

    By default, uses incremental mode (--skip-unchanged) to only upload changed lookup files.
    Use --no-skip-unchanged to force upload all files (slower but ensures consistency).

    Examples:
        # Generate and save locally
        parselmouth update-relations-table --output-dir ./output

        # Generate and upload to S3 (CI/production) - incremental mode
        parselmouth update-relations-table --upload

        # Force upload all files (full mode)
        parselmouth update-relations-table --upload --no-skip-unchanged

        # Both save locally and upload
        parselmouth update-relations-table --upload --output-dir ./output
    """
    relations_updater_main(channel=channel, upload=upload, output_dir=output_dir, skip_unchanged=skip_unchanged)


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
    backend: Optional[str] = None,
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
):
    """
    Check mapping just for one package.
    You can also upload it to S3.
    """

    check_one_main(
        package_name=package_name, subdir=subdir, backend_type=backend, upload=upload
    )


@app.command()
def remove(
    subdir: Annotated[
        str,
        typer.Argument(help="Subdir for the package name"),
    ],
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    dry_run: bool = True,
):
    """
    Yank and remove packages from the index and by it's hash.
    """

    remover_main(
        subdir=subdir,
        channel=channel,
        dry_run=dry_run,
    )


@app.command()
def explore(
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
):
    """
    Interactive Conda -> PyPI package explorer with rich interface.

    This provides an interactive way to explore conda packages and discover
    their corresponding PyPI mappings:

    1. Select platform/subdir (linux-64, osx-arm64, etc.)
    2. Search for conda packages (with suggestions)
    3. Browse versions (with pagination and direct input)
    4. View build details in a table
    5. View PyPI mapping:
       - Aggregated across all builds (default)
       - For a specific build
       - Or skip

    Note: This explores the Conda -> PyPI direction. A PyPI -> Conda explorer
    will be available in the future.
    """

    explore_package(channel=channel)
