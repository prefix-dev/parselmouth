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
from parselmouth.explorer import explore_package

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
def update_v1_mappings(
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    upload: bool = False,
    output_dir: Optional[str] = None,
    skip_unchanged: bool = True,
    public_url: bool = False,
):
    """
    Generate and upload v1 mappings (relations table + PyPI lookup files).

    This creates:
    - Master relations table (JSONL) at /relations-v1/{channel}/relations.jsonl.gz
    - Relations metadata at /relations-v1/{channel}/metadata.json
    - PyPI -> Conda lookup files at /pypi-to-conda-v1/{channel}/{pypi_name}.json

    The v1 format is table-based and serves as the single source of truth.
    Both Conda->PyPI and PyPI->Conda lookups are derived from this table.

    By default, uses incremental mode (--skip-unchanged) to only upload changed lookup files.
    Use --no-skip-unchanged to force upload all files (slower but ensures consistency).

    Use --public-url to download index from public HTTPS URL (no R2 credentials needed).
    This is useful for local testing without R2 access.

    Examples:
        # Generate and save locally (no credentials needed)
        parselmouth update-v1-mappings --output-dir ./output --public-url

        # Generate and upload to S3 (CI/production) - incremental mode
        parselmouth update-v1-mappings --upload --channel conda-forge

        # Force upload all files (full mode)
        parselmouth update-v1-mappings --upload --no-skip-unchanged

        # Both save locally and upload
        parselmouth update-v1-mappings --upload --output-dir ./output
    """
    relations_updater_main(
        channel=channel,
        upload=upload,
        output_dir=output_dir,
        skip_unchanged=skip_unchanged,
        public_url=public_url,
    )


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
    endpoint: str = typer.Option(
        None,
        help="Endpoint to use: 'production' or 'local' (interactive prompt if not specified)",
    ),
    subdir: str = typer.Option(
        None,
        help="Platform/subdir for non-interactive mode (e.g., 'linux-64', 'noarch')",
    ),
    package_name: str = typer.Option(
        None,
        "--package-name",
        help="Package name for non-interactive mode",
    ),
    version: str = typer.Option(
        None,
        help="Package version for non-interactive mode",
    ),
    build: str = typer.Option(
        None,
        help="Build string for non-interactive mode",
    ),
):
    """
    Interactive Conda -> PyPI package explorer (HTTP-based).

    This provides an interactive way to explore conda packages and discover
    their corresponding PyPI mappings via HTTP endpoints (production or local MinIO).

    INTERACTIVE MODE (default):
    1. Select endpoint (production or local MinIO)
    2. NOTE: Full conda browsing not yet implemented with HTTP-only
    3. Use PyPI explorer or direct hash lookups for now

    NON-INTERACTIVE MODE (for testing):
    Provide --endpoint, --package-name, --version to skip prompts.

    Examples:
      # Interactive
      parselmouth explore --endpoint local

      # Non-interactive (testing)
      parselmouth explore --endpoint local --package-name numpy --version 1.26.4
    """
    # Convert endpoint string to base_url
    base_url = None
    if endpoint == "production":
        base_url = "https://conda-mapping.prefix.dev"
    elif endpoint == "local":
        base_url = "http://localhost:9000/conda"
    elif endpoint is not None:
        typer.echo(f"Invalid endpoint: {endpoint}. Use 'production' or 'local'.")
        raise typer.Exit(1)

    explore_package(
        channel=channel,
        base_url=base_url,
        subdir=subdir,
        package_name=package_name,
        version=version,
        build=build,
    )


@app.command()
def explore_pypi(
    endpoint: str = typer.Option(
        None,
        help="Endpoint to use: 'production' or 'local' (interactive prompt if not specified)",
    ),
    channel: SupportedChannels = typer.Option(
        None,
        help="Conda channel (interactive prompt if not specified)",
    ),
    pypi_name: str = typer.Option(
        None,
        "--pypi-name",
        help="PyPI package name for non-interactive mode",
    ),
    version: str = typer.Option(
        None,
        help="PyPI version for non-interactive mode",
    ),
):
    """
    Interactive PyPI -> Conda package explorer (HTTP-based).

    This provides an interactive way to explore PyPI packages and discover
    which conda versions are available across different channels.

    INTERACTIVE MODE (default):
    1. Select endpoint (production or local MinIO)
    2. Select conda channel (conda-forge, pytorch, bioconda)
    3. Enter PyPI package name
    4. View all available conda versions
    5. Optional: Drill down to specific version for details

    NON-INTERACTIVE MODE (for testing):
    Provide --endpoint, --channel, --pypi-name to skip prompts.

    Examples:
      # Interactive
      parselmouth explore-pypi

      # Interactive with local MinIO
      parselmouth explore-pypi --endpoint local

      # Non-interactive (testing)
      parselmouth explore-pypi --endpoint local --channel conda-forge --pypi-name requests

      # View specific version
      parselmouth explore-pypi --endpoint production --channel conda-forge --pypi-name numpy --version 1.26.4
    """
    from parselmouth.explorer import explore_pypi_package

    # Convert endpoint string to base_url
    base_url = None
    if endpoint == "production":
        base_url = "https://conda-mapping.prefix.dev"
    elif endpoint == "local":
        base_url = "http://localhost:9000/conda"
    elif endpoint is not None:
        typer.echo(f"Invalid endpoint: {endpoint}. Use 'production' or 'local'.")
        raise typer.Exit(1)

    explore_pypi_package(
        channel=channel,
        base_url=base_url,
        pypi_name=pypi_name,
        version=version,
    )


@app.command()
def cache_info():
    """
    Show information about cached channel indices.

    Displays cache location, size, and metadata for all cached index files.
    """
    from parselmouth.explorer.index_cache import get_cache_dir, get_cache_info
    from datetime import datetime

    cache_dir = get_cache_dir()
    typer.echo(f"\n📁 Cache directory: {cache_dir}\n")

    info = get_cache_info()

    if not info:
        typer.echo("No cached indices found.\n")
        return

    typer.echo(f"Found {len(info)} cached index file(s):\n")

    for filename, data in sorted(info.items()):
        typer.echo(f"  📦 {filename}")
        typer.echo(
            f"     Size: {data['size_mb']:.2f} MB ({data['size_bytes']:,} bytes)"
        )

        if mtime := data.get("modified_time"):
            dt = datetime.fromtimestamp(mtime)
            typer.echo(f"     Modified: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

        if etag := data.get("etag"):
            typer.echo(
                f"     ETag: {etag[:50]}..." if len(etag) > 50 else f"     ETag: {etag}"
            )

        if last_mod := data.get("last_modified"):
            typer.echo(f"     Last-Modified: {last_mod}")

        typer.echo()

    total_size_mb = sum(d["size_mb"] for d in info.values())
    typer.echo(f"Total cache size: {total_size_mb:.2f} MB\n")


@app.command()
def cache_clear(
    channel: SupportedChannels = typer.Option(
        None,
        help="Clear cache for specific channel only",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """
    Clear cached channel indices.

    By default, clears all cached indices. Use --channel to clear only a specific channel.
    """
    from parselmouth.explorer.index_cache import clear_cache, get_cache_info

    # Show what will be cleared
    info = get_cache_info()

    if not info:
        typer.echo("No cached indices to clear.\n")
        return

    if channel:
        typer.echo(f"Will clear cache for channel: {channel}\n")
    else:
        typer.echo("Will clear ALL cached indices:\n")
        for filename, data in info.items():
            typer.echo(f"  - {filename} ({data['size_mb']:.2f} MB)")
        typer.echo()

    # Confirm unless --force
    if not force:
        confirm = typer.confirm("Are you sure you want to clear the cache?")
        if not confirm:
            typer.echo("Cancelled.")
            return

    # Clear cache
    removed = clear_cache(channel)
    typer.echo(f"\n✓ Cleared {removed} cached index file(s).\n")
