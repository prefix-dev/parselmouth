"""Interactive explorer entry points and supporting helpers."""

from __future__ import annotations

from packaging.version import Version, InvalidVersion
from rich.prompt import Prompt
from rich.panel import Panel

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import MappingEntry

from .common import console, logger
from .catalog import PackageCatalog
from .loader import PackageIndexLoader
from .selectors import (
    EndpointSelector,
    ChannelSelector,
    CondaPackageSelector,
    VersionSelector,
)
from .renderers import BuildTableRenderer, PyPIVersionTableRenderer
from .http_client import (
    fetch_channel_index_http,
    fetch_mapping_entry_by_hash,
    fetch_pypi_lookup,
)


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


def select_endpoint_interactive() -> str:
    """Prompt user to select endpoint (production or local MinIO)."""
    return EndpointSelector().resolve()


def normalize_pypi_name(name: str) -> str:
    """Normalize PyPI package name (lowercase, hyphens to underscores)."""
    return name.lower().replace("-", "_")


def sort_versions_descending(
    versions: dict[str, str],
) -> list[tuple[str, str]]:
    """Sort PyPI versions newest to oldest using packaging.version."""

    def version_key(item: tuple[str, str]) -> Version | str:
        version_str, _ = item
        try:
            return Version(version_str)
        except InvalidVersion:
            return version_str

    items = list(versions.items())
    try:
        return sorted(items, key=version_key, reverse=True)
    except TypeError:
        return sorted(items, key=lambda x: x[0], reverse=True)


def get_packages_from_index_http(
    channel: SupportedChannels,
    base_url: str,
) -> dict[str, dict[str, MappingEntry]]:
    console.print("\n[bold green]Fetching channel index via HTTP...[/bold green]")

    with console.status("[bold green]Downloading index..."):
        index = fetch_channel_index_http(channel, base_url=base_url)

    if not index:
        console.print("[red]✗[/red] Failed to fetch channel index")
        return {}

    by_subdir: dict[str, dict[str, MappingEntry]] = {}

    for filename, entry in index.root.items():
        parts = filename.split("/")
        if len(parts) > 1:
            subdir = parts[0]
        else:
            subdir = "unknown"

        if subdir not in by_subdir:
            by_subdir[subdir] = {}
        by_subdir[subdir][filename] = entry

    if len(by_subdir) == 1 and "unknown" in by_subdir:
        console.print(f"[green]✓[/green] Loaded {len(index.root)} packages from index")
    else:
        total = sum(len(packages) for packages in by_subdir.values())
        console.print(
            f"[green]✓[/green] Loaded {total} packages across {len(by_subdir)} subdirs"
        )

    return by_subdir


def fetch_package_mapping_http(sha256: str, base_url: str) -> MappingEntry | None:
    entry = fetch_mapping_entry_by_hash(sha256, base_url=base_url)
    if not entry:
        logger.warning(f"No mapping found for hash: {sha256}")
    return entry


def explore_package(
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
    base_url: str | None = None,
    subdir: str | None = None,
    package_name: str | None = None,
    version: str | None = None,
    build: str | None = None,
):
    console.print("\n[bold cyan]🔍 Conda → PyPI Package Explorer (HTTP)[/bold cyan]\n")

    base_url = EndpointSelector().resolve(base_url)

    console.print(
        Panel.fit(
            f"[cyan]Channel:[/cyan] {channel}\n[cyan]Endpoint:[/cyan] {base_url}",
            title="Exploration Context",
            border_style="cyan",
        )
    )

    loader = PackageIndexLoader(channel=channel, base_url=base_url)
    index, cache_status = loader.load()
    if not index:
        return

    console.print("[yellow]Organizing packages...[/yellow]")
    catalog = PackageCatalog.from_index_cached(
        index,
        channel=channel,
        base_url=base_url,
        cache_status=cache_status,
        show_progress=True,
    )
    console.print(
        f"[green]✓[/green] Found {len(catalog.packages_by_name)} unique package names\n"
    )

    selector = CondaPackageSelector(catalog=catalog)
    try:
        selected_package, versions_dict = selector.select(
            package_name, prompt_on_multiple=(version is None)
        )
    except ValueError:
        return

    console.print(f"\n[green]✓[/green] Selected: {selected_package}\n")

    version_selector = VersionSelector()
    selected_version = version_selector.select(versions_dict, version)
    if not selected_version:
        return

    console.print(f"\n[green]✓[/green] Selected version: {selected_version}\n")

    console.print(
        Panel.fit(
            f"[cyan]Package:[/cyan] {selected_package}\n[cyan]Version:[/cyan] {selected_version}",
            title="Selection",
            border_style="green",
        )
    )

    builds = versions_dict[selected_version]
    console.print(
        f"[yellow]Found {len(builds)} build(s) for {selected_package}-{selected_version}[/yellow]\n"
    )

    BuildTableRenderer().render(selected_package, selected_version, builds)

    console.print("\n[green]✓[/green] Exploration complete!")
    console.print(
        f"[dim]Package: {selected_package}, Version: {selected_version}, Builds: {len(builds)}[/dim]\n"
    )


def explore_pypi_package(
    channel: SupportedChannels | None = None,
    base_url: str | None = None,
    pypi_name: str | None = None,
    version: str | None = None,
):
    console.print("\n[bold cyan]🔍 PyPI → Conda Package Explorer (HTTP)[/bold cyan]\n")

    base_url = EndpointSelector().resolve(base_url)
    channel = ChannelSelector().resolve(channel)

    console.print(
        Panel.fit(
            f"[cyan]Endpoint:[/cyan] {base_url}\n[cyan]Channel:[/cyan] {channel}",
            title="Exploration Context",
            border_style="cyan",
        )
    )

    if pypi_name is None:
        console.print("\n[yellow]Enter PyPI Package Name[/yellow]")
        pypi_name = Prompt.ask("PyPI package name")

    normalized_name = normalize_pypi_name(pypi_name)
    if normalized_name != pypi_name:
        console.print(f"[dim]Normalized to: {normalized_name}[/dim]")

    console.print(f"\n[green]✓[/green] Looking up: {normalized_name}")

    with console.status("[bold green]Fetching PyPI → Conda mappings..."):
        lookup = fetch_pypi_lookup(channel, normalized_name, base_url=base_url)

    if not lookup:
        console.print(
            f"\n[red]✗[/red] No conda packages found for '{normalized_name}' in {channel}"
        )
        console.print("[dim]This package may not be available in this channel.[/dim]")
        return

    console.print(
        f"[green]✓[/green] Found {len(lookup.conda_versions)} PyPI versions in {channel}\n"
    )

    sorted_versions = sort_versions_descending(lookup.conda_versions)
    renderer = PyPIVersionTableRenderer()

    if version:
        if version in lookup.conda_versions:
            renderer.render_detail(
                normalized_name,
                version,
                lookup.conda_versions[version],
                channel,
            )
        else:
            console.print(f"[red]✗[/red] Version {version} not found")
            console.print(
                f"[dim]Available versions: {', '.join([v for v, _ in sorted_versions[:5]])}...[/dim]"
            )
        return

    renderer.render_overview(normalized_name, channel, sorted_versions)


__all__ = [
    "explore_package",
    "explore_pypi_package",
    "fetch_package_mapping_http",
    "get_packages_from_index_http",
    "normalize_pypi_name",
    "select_endpoint_interactive",
    "sort_versions_descending",
    "format_size",
]
