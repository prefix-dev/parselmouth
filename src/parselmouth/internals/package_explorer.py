"""
Interactive Conda <-> PyPI package explorer using Rich for a better UX.

This provides HTTP-based interactive interfaces to:
1. Explore conda packages and discover their corresponding PyPI mappings (Conda → PyPI)
2. Explore PyPI packages and discover available conda versions (PyPI → Conda)

All data is fetched via HTTP from either production (https://conda-mapping.prefix.dev)
or local MinIO (http://localhost:9000/conda).
"""

import logging
from datetime import datetime
from typing import Literal

from packaging.version import Version, InvalidVersion
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.index_cache import fetch_channel_index_cached
from parselmouth.internals.mapping_http_client import (
    fetch_channel_index_http,
    fetch_mapping_entry_by_hash,
    fetch_pypi_lookup,
)
from parselmouth.internals.s3 import IndexMapping, MappingEntry
from parselmouth.internals.package_relations import PyPIPackageLookup


console = Console()
logger = logging.getLogger(__name__)

# Endpoint URLs
PRODUCTION_URL = "https://conda-mapping.prefix.dev"
LOCAL_MINIO_URL = "http://localhost:9000/conda"


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
    console.print("\n[yellow]Select Endpoint[/yellow]")
    console.print("1. Production (https://conda-mapping.prefix.dev)")
    console.print("2. Local MinIO (http://localhost:9000/conda)")

    choice = Prompt.ask("\nSelect endpoint", choices=["1", "2"], default="1")

    if choice == "1":
        console.print("[green]✓[/green] Using production endpoint")
        return PRODUCTION_URL
    else:
        console.print("[green]✓[/green] Using local MinIO endpoint")
        return LOCAL_MINIO_URL


def normalize_pypi_name(name: str) -> str:
    """
    Normalize PyPI package name (lowercase, hyphens to underscores).

    This follows PEP 503 normalization rules.
    """
    return name.lower().replace("-", "_")


def sort_versions_descending(versions: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """
    Sort PyPI versions newest to oldest using packaging.version.

    Args:
        versions: Dict of version -> list of conda packages

    Returns:
        List of (version, conda_packages) tuples, sorted newest first
    """
    def version_key(item):
        version_str, _ = item
        try:
            return Version(version_str)
        except InvalidVersion:
            # Fall back to string comparison for invalid versions
            return version_str

    items = list(versions.items())
    try:
        return sorted(items, key=version_key, reverse=True)
    except TypeError:
        # If comparison fails, fall back to string sorting
        return sorted(items, key=lambda x: x[0], reverse=True)


def get_packages_from_index_http(
    channel: SupportedChannels,
    base_url: str,
) -> dict[str, dict[str, MappingEntry]]:
    """
    Fetch channel index via HTTP and organize packages by subdir.

    Args:
        channel: The conda channel to fetch
        base_url: Base URL for HTTP requests

    Returns:
        Dict mapping subdir -> {package_filename: MappingEntry}
    """
    console.print("\n[bold green]Fetching channel index via HTTP...[/bold green]")

    with console.status("[bold green]Downloading index..."):
        index = fetch_channel_index_http(channel, base_url=base_url)

    if not index:
        console.print("[red]✗[/red] Failed to fetch channel index")
        return {}

    # Organize by subdir
    # The index.root is a dict of {filename: MappingEntry}
    # We need to extract subdir from the filename
    by_subdir: dict[str, dict[str, MappingEntry]] = {}

    for filename, entry in index.root.items():
        # Extract subdir from filename path if it exists
        # Format is typically: subdir/package-version-build.conda
        # But the index may store just the filename
        # We'll infer from the package_name in the entry

        # For now, we'll need to parse from the actual package structure
        # Most indices don't include subdir, so we may need to fetch from somewhere else
        # Let's just put everything in a generic bucket for now and let user browse
        parts = filename.split("/")
        if len(parts) > 1:
            subdir = parts[0]
        else:
            subdir = "unknown"

        if subdir not in by_subdir:
            by_subdir[subdir] = {}
        by_subdir[subdir][filename] = entry

    # If everything is in "unknown", it means the index doesn't include subdir info
    # In this case, we need a different approach - just return all packages
    if len(by_subdir) == 1 and "unknown" in by_subdir:
        console.print(f"[green]✓[/green] Loaded {len(index.root)} packages from index")
    else:
        total = sum(len(packages) for packages in by_subdir.values())
        console.print(f"[green]✓[/green] Loaded {total} packages across {len(by_subdir)} subdirs")

    return by_subdir


def fetch_package_mapping_http(sha256: str, base_url: str) -> MappingEntry | None:
    """
    Fetch single package mapping via HTTP.

    Args:
        sha256: Package SHA256 hash
        base_url: Base URL for HTTP requests

    Returns:
        MappingEntry or None if not found
    """
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
    """
    Interactive Conda → PyPI package explorer (HTTP-based).

    Interactive flow (when params not provided):
    1. Select endpoint (production or local)
    2. Enter package name to search
    3. Select version
    4. Display all builds with PyPI mappings

    Non-interactive mode (for testing):
    Provide package_name, version, and optionally build to skip prompts.

    Args:
        channel: Conda channel to explore
        base_url: Base URL for HTTP requests (if None, prompts user)
        subdir: Platform/subdir (not used currently, kept for compatibility)
        package_name: Package name to explore
        version: Package version
        build: Specific build string (optional)
    """
    console.print("\n[bold cyan]🔍 Conda → PyPI Package Explorer (HTTP)[/bold cyan]\n")

    # Step 0: Select endpoint if not provided
    if base_url is None:
        base_url = select_endpoint_interactive()

    console.print(f"\n[cyan]Channel:[/cyan] {channel}")
    console.print(f"[cyan]Endpoint:[/cyan] {base_url}\n")

    # Step 1: Fetch the channel index (with caching)
    # Use a status display that updates in real-time
    current_status = ["Initializing..."]  # Use list to allow mutation in callback

    def update_status(message: str):
        """Callback to update status message."""
        current_status[0] = message

    with console.status("[bold green]Checking for updates...") as status:
        # Define callback that updates the status
        def progress_callback(msg: str):
            update_status(msg)
            status.update(f"[bold green]{msg}")

        # Fetch with progress updates
        index, cache_status = fetch_channel_index_cached(
            channel,
            base_url,
            progress_callback=progress_callback
        )

    if not index:
        console.print("[red]✗[/red] Failed to fetch channel index")
        console.print("[dim]Make sure the endpoint is accessible and contains data for this channel.[/dim]")
        return

    console.print(f"[green]✓[/green] Loaded {len(index.root)} package mappings [dim]({cache_status})[/dim]\n")

    # Step 2: Organize packages by conda name and version
    # Index structure: {hash: MappingEntry}
    # MappingEntry has: conda_name, package_name (with version-build), pypi info

    packages_by_name: dict[str, dict[str, list[tuple[str, MappingEntry]]]] = {}
    # Structure: {conda_name: {version: [(hash, entry)]}}

    console.print("[yellow]Organizing packages...[/yellow]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[green]Processing index...", total=None)

        for pkg_hash, entry in index.root.items():
            conda_name = entry.conda_name
            # Extract version from package_name
            # Format: package-version-build.tar.bz2 or .conda
            pkg_filename = entry.package_name
            # Remove extension
            pkg_base = pkg_filename.replace(".tar.bz2", "").replace(".conda", "")
            # Split by hyphens: package-version-build
            parts = pkg_base.rsplit("-", 2)
            if len(parts) >= 2:
                pkg_version = parts[1]
            else:
                pkg_version = "unknown"

            if conda_name not in packages_by_name:
                packages_by_name[conda_name] = {}
            if pkg_version not in packages_by_name[conda_name]:
                packages_by_name[conda_name][pkg_version] = []

            packages_by_name[conda_name][pkg_version].append((pkg_hash, entry))

    console.print(f"[green]✓[/green] Found {len(packages_by_name)} unique package names\n")

    # Step 3: Get package name if not provided
    if package_name is None:
        console.print("[yellow]Enter Package Name[/yellow]")
        console.print("[dim]Tip: Enter a partial name to search[/dim]")
        package_name = Prompt.ask("\nPackage name")

    # Search for matching packages
    # First try exact match
    if package_name in packages_by_name:
        matching_packages = {package_name: packages_by_name[package_name]}
    else:
        # Then try substring match
        matching_packages = {
            name: versions
            for name, versions in packages_by_name.items()
            if package_name.lower() in name.lower()
        }

    if not matching_packages:
        console.print(f"[red]✗[/red] No packages found matching '{package_name}'")
        # Show some suggestions
        suggestions = sorted(packages_by_name.keys())[:20]
        console.print("\n[dim]Some available packages:[/dim]")
        for suggestion in suggestions:
            console.print(f"  - {suggestion}")
        return

    if len(matching_packages) > 50:
        console.print(f"[yellow]⚠[/yellow] Found {len(matching_packages)} matching packages. Showing first 50.")
        console.print("[dim]Be more specific to narrow down results.[/dim]\n")
        matching_packages = dict(list(matching_packages.items())[:50])

    # If multiple matches, let user choose (unless in non-interactive mode)
    if len(matching_packages) > 1 and version is None:
        console.print("\n[cyan]Found multiple packages:[/cyan]")
        pkg_list = sorted(matching_packages.keys())
        for idx, name in enumerate(pkg_list[:20], 1):
            version_count = len(matching_packages[name])
            console.print(f"  {idx}. {name} ({version_count} version{'s' if version_count > 1 else ''})")

        if len(pkg_list) > 20:
            console.print(f"  [dim]... and {len(pkg_list) - 20} more[/dim]")

        choice = Prompt.ask(
            "\nSelect package number",
            choices=[str(i) for i in range(1, min(len(pkg_list), 20) + 1)],
            default="1",
        )
        selected_package = pkg_list[int(choice) - 1]
    else:
        selected_package = list(matching_packages.keys())[0]

    console.print(f"\n[green]✓[/green] Selected: {selected_package}\n")

    # Step 4: Show versions
    versions_dict = matching_packages[selected_package]

    if version is None:
        console.print("[yellow]Available Versions[/yellow]")
        sorted_versions = sorted(versions_dict.keys(), key=lambda v: _version_sort_key(v), reverse=True)

        # Show versions
        for idx, ver in enumerate(sorted_versions[:30], 1):
            build_count = len(versions_dict[ver])
            console.print(f"  {idx}. {ver} ({build_count} build{'s' if build_count > 1 else ''})")

        if len(sorted_versions) > 30:
            console.print(f"  [dim]... and {len(sorted_versions) - 30} more versions[/dim]")

        version_choice = Prompt.ask("\nEnter version number or version string", default="1")

        # Check if it's a number
        if version_choice.isdigit():
            choice_num = int(version_choice)
            if 1 <= choice_num <= min(len(sorted_versions), 30):
                version = sorted_versions[choice_num - 1]
            else:
                console.print(f"[red]Invalid choice[/red]")
                return
        else:
            # Direct version string
            if version_choice in versions_dict:
                version = version_choice
            else:
                console.print(f"[red]Version '{version_choice}' not found[/red]")
                return

    console.print(f"\n[green]✓[/green] Selected version: {version}\n")

    # Step 5: Display builds and their PyPI mappings
    if version not in versions_dict:
        console.print(f"[red]✗[/red] Version {version} not found")
        return

    builds = versions_dict[version]
    console.print(f"[yellow]Found {len(builds)} build(s) for {selected_package}-{version}[/yellow]\n")

    # Create table showing builds and PyPI mappings
    table = Table(
        title=f"{selected_package}-{version} Builds and PyPI Mappings",
        show_header=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Build String", style="cyan")
    table.add_column("Package Filename", style="white")
    table.add_column("PyPI Package(s)", style="green")
    table.add_column("PyPI Version(s)", style="yellow")

    for idx, (pkg_hash, entry) in enumerate(sorted(builds, key=lambda x: x[1].package_name), 1):
        # Extract build string
        pkg_base = entry.package_name.replace(".tar.bz2", "").replace(".conda", "")
        parts = pkg_base.rsplit("-", 2)
        build_string = parts[2] if len(parts) >= 3 else "unknown"

        # Format PyPI info
        if entry.pypi_normalized_names:
            pypi_pkgs = ", ".join(entry.pypi_normalized_names[:3])
            if len(entry.pypi_normalized_names) > 3:
                pypi_pkgs += f", ... (+{len(entry.pypi_normalized_names) - 3})"
        else:
            pypi_pkgs = "[dim]None[/dim]"

        if entry.versions:
            pypi_versions = ", ".join([f"{v}" for v in list(entry.versions.values())[:3]])
            if len(entry.versions) > 3:
                pypi_versions += f", ... (+{len(entry.versions) - 3})"
        else:
            pypi_versions = "[dim]N/A[/dim]"

        table.add_row(
            str(idx),
            build_string,
            entry.package_name,
            pypi_pkgs,
            pypi_versions,
        )

    console.print(table)

    # Summary
    console.print(f"\n[green]✓[/green] Exploration complete!")
    console.print(f"[dim]Package: {selected_package}, Version: {version}, Builds: {len(builds)}[/dim]\n")


def _version_sort_key(version_str: str):
    """Helper to sort versions, handling invalid versions."""
    try:
        return Version(version_str)
    except InvalidVersion:
        return version_str


def explore_pypi_package(
    channel: SupportedChannels | None = None,
    base_url: str | None = None,
    pypi_name: str | None = None,
    version: str | None = None,
):
    """
    Interactive PyPI → Conda package explorer (HTTP-based).

    Interactive flow (when params not provided):
    1. Select endpoint (production or local)
    2. Select channel (conda-forge, pytorch, bioconda)
    3. Enter PyPI package name
    4. View all conda versions available
    5. Optional: Drill down to specific version for details

    Non-interactive mode (for testing):
    Provide channel, base_url, pypi_name, and optionally version.

    Args:
        channel: Conda channel (if None, prompts interactively)
        base_url: Base URL for HTTP requests (if None, prompts interactively)
        pypi_name: PyPI package name
        version: Specific PyPI version to view (optional)
    """
    console.print("\n[bold cyan]🔍 PyPI → Conda Package Explorer (HTTP)[/bold cyan]\n")

    # Step 1: Select endpoint if not provided
    if base_url is None:
        base_url = select_endpoint_interactive()

    console.print(f"\n[cyan]Endpoint:[/cyan] {base_url}")

    # Step 2: Select channel if not provided
    if channel is None:
        console.print("\n[yellow]Select Channel[/yellow]")
        console.print("1. conda-forge")
        console.print("2. pytorch")
        console.print("3. bioconda")

        choice = Prompt.ask("\nSelect channel", choices=["1", "2", "3"], default="1")

        if choice == "1":
            channel = SupportedChannels.CONDA_FORGE
        elif choice == "2":
            channel = SupportedChannels.PYTORCH
        else:
            channel = SupportedChannels.BIOCONDA

    console.print(f"[green]✓[/green] Using channel: {channel}")

    # Step 3: Get PyPI package name if not provided
    if pypi_name is None:
        console.print("\n[yellow]Enter PyPI Package Name[/yellow]")
        pypi_name = Prompt.ask("PyPI package name")

    # Normalize the name
    normalized_name = normalize_pypi_name(pypi_name)
    if normalized_name != pypi_name:
        console.print(f"[dim]Normalized to: {normalized_name}[/dim]")

    console.print(f"\n[green]✓[/green] Looking up: {normalized_name}")

    # Step 4: Fetch PyPI lookup data
    with console.status("[bold green]Fetching PyPI → Conda mappings..."):
        lookup = fetch_pypi_lookup(channel, normalized_name, base_url=base_url)

    if not lookup:
        console.print(f"\n[red]✗[/red] No conda packages found for '{normalized_name}' in {channel}")
        console.print("[dim]This package may not be available in this channel.[/dim]")
        return

    console.print(f"[green]✓[/green] Found {len(lookup.conda_versions)} PyPI versions in {channel}\n")

    # Step 5: Display versions
    sorted_versions = sort_versions_descending(lookup.conda_versions)

    # If specific version requested, show only that
    if version:
        if version in lookup.conda_versions:
            _display_single_pypi_version(
                normalized_name,
                version,
                lookup.conda_versions[version],
                channel,
                base_url,
            )
        else:
            console.print(f"[red]✗[/red] Version {version} not found")
            console.print(f"[dim]Available versions: {', '.join([v for v, _ in sorted_versions[:5]])}...[/dim]")
        return

    # Display all versions in a table
    table = Table(
        title=f"PyPI Package: {normalized_name} (Channel: {channel})",
        show_header=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("PyPI Version", style="green")
    table.add_column("Conda Packages", style="cyan")

    for idx, (pypi_version, conda_packages) in enumerate(sorted_versions, 1):
        # Format conda packages list
        if len(conda_packages) <= 3:
            packages_str = ", ".join(conda_packages)
        else:
            packages_str = f"{', '.join(conda_packages[:3])}, ... (+{len(conda_packages)-3} more)"

        table.add_row(str(idx), pypi_version, packages_str)

    console.print(table)

    # Step 6: Optional drill-down
    console.print("\n[yellow]View Details (optional)[/yellow]")
    console.print("[dim]Options:[/dim]")
    console.print("  - Type a number to view that version's details")
    console.print("  - Type 'n' to exit")

    detail_choice = Prompt.ask("\nYour choice", default="n")

    if detail_choice.lower() == "n":
        console.print("\n[dim]Exiting explorer[/dim]")
        return

    # Check if it's a number
    if detail_choice.isdigit():
        choice_num = int(detail_choice)
        if 1 <= choice_num <= len(sorted_versions):
            selected_version, conda_packages = sorted_versions[choice_num - 1]
            _display_single_pypi_version(
                normalized_name,
                selected_version,
                conda_packages,
                channel,
                base_url,
            )
        else:
            console.print(f"[red]Invalid choice. Please enter 1-{len(sorted_versions)}[/red]")


def _display_single_pypi_version(
    pypi_name: str,
    pypi_version: str,
    conda_packages: list[str],
    channel: SupportedChannels,
    base_url: str,
):
    """
    Display detailed information about conda packages for a specific PyPI version.

    This optionally fetches hash mappings to show build details.
    """
    console.print(f"\n[bold cyan]📦 Details for {pypi_name}=={pypi_version}[/bold cyan]\n")

    # Create table
    table = Table(title=f"Conda Packages (Channel: {channel})", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Conda Package Name", style="cyan")

    for idx, conda_pkg in enumerate(conda_packages, 1):
        table.add_row(str(idx), conda_pkg)

    console.print(table)

    console.print(f"\n[green]✓[/green] {len(conda_packages)} conda package(s) provide {pypi_name}=={pypi_version}")

    # Note about hash lookups
    console.print("\n[dim]Note: To view build details (size, timestamp, etc.), you need the package hash.[/dim]")
    console.print("[dim]Hash lookups can be added here in a future enhancement.[/dim]")
