"""
Interactive Conda -> PyPI package explorer using Rich for a better UX.

This provides an interactive interface to explore conda packages and discover
their corresponding PyPI mappings.
"""

import logging

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
from parselmouth.internals.conda_forge import (
    get_all_packages_by_subdir,
    get_artifact_info,
)
from parselmouth.internals.artifact import extract_artifact_mapping


console = Console()
logger = logging.getLogger(__name__)


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


def explore_package(
    channel: SupportedChannels = SupportedChannels.CONDA_FORGE,
):
    """
    Interactive Conda -> PyPI package explorer.

    1. Select platform/subdir
    2. Enter package name (with suggestions if not found)
    3. Select version
    4. Display all builds with metadata
    5. Optionally view PyPI mapping
    """
    console.print("\n[bold cyan]🔍 Conda → PyPI Package Explorer[/bold cyan]\n")

    # Step 1: Get subdir/platform
    console.print("[yellow]Step 1: Select Platform/Subdir[/yellow]")
    console.print("Common options: linux-64, osx-64, osx-arm64, win-64, noarch")

    subdir = Prompt.ask("Enter subdir", default="linux-64")

    console.print(f"\n[green]✓[/green] Using subdir: {subdir}")

    # Step 2: Get package name
    console.print("\n[yellow]Step 2: Enter Package Name[/yellow]")

    with console.status("[bold green]Loading repodata..."):
        repodatas = get_all_packages_by_subdir(subdir, channel)

    # Flatten all packages from all labels
    all_packages = {}
    for label, packages in repodatas.items():
        all_packages.update(packages)

    console.print(f"[dim]Loaded {len(all_packages)} packages from {subdir}[/dim]")

    package_name_input = Prompt.ask("\nEnter package name (without version)")

    # Find matching packages
    matching_packages = {
        name: info
        for name, info in all_packages.items()
        if package_name_input.lower() in name.lower()
    }

    if not matching_packages:
        console.print(f"[red]✗[/red] No packages found matching '{package_name_input}'")

        # Show some suggestions
        suggestions = [name for name in list(all_packages.keys())[:20]]
        console.print("\n[dim]Some available packages:[/dim]")
        for suggestion in suggestions:
            console.print(f"  - {suggestion}")
        return

    if len(matching_packages) > 100:
        console.print(
            f"[yellow]⚠[/yellow] Found {len(matching_packages)} matching packages. Showing first 100."
        )
        console.print("[dim]Be more specific to narrow down results.[/dim]\n")
        matching_packages = dict(list(matching_packages.items())[:100])

    # Group by base package name (remove version and build)
    base_packages: dict[str, list[str]] = {}
    for full_name in matching_packages.keys():
        # Extract base name by removing version suffix
        # e.g., "numpy-1.26.4-py311_0" -> "numpy"
        parts = full_name.rsplit("-", 2)
        if len(parts) >= 3:
            base_name = parts[0]
            if base_name not in base_packages:
                base_packages[base_name] = []
            base_packages[base_name].append(full_name)

    if len(base_packages) > 1:
        console.print("\n[cyan]Found multiple packages:[/cyan]")
        base_list = sorted(base_packages.keys())
        for idx, base in enumerate(base_list, 1):
            console.print(f"  {idx}. {base} ({len(base_packages[base])} versions)")

        choice = Prompt.ask(
            "\nSelect package number",
            choices=[str(i) for i in range(1, len(base_list) + 1)],
            default="1",
        )
        selected_base = base_list[int(choice) - 1]
    else:
        selected_base = list(base_packages.keys())[0]

    console.print(f"\n[green]✓[/green] Selected package: {selected_base}")

    # Step 3: Show versions
    console.print("\n[yellow]Step 3: Select Version[/yellow]")

    package_versions = base_packages[selected_base]

    # Group by version (without build) and calculate total size
    versions: dict[str, list[str]] = {}
    version_sizes: dict[str, int] = {}
    for full_name in package_versions:
        parts = full_name.rsplit("-", 2)
        if len(parts) >= 3:
            version = parts[1]
            if version not in versions:
                versions[version] = []
                version_sizes[version] = 0
            versions[version].append(full_name)

            # Add up the size for this build
            size = matching_packages[full_name].get("size", 0)
            if isinstance(size, int):
                version_sizes[version] += size

    sorted_versions = sorted(versions.keys(), reverse=True)

    # Show versions in pages
    page_size = 20
    current_page = 0

    while True:
        start_idx = current_page * page_size
        end_idx = start_idx + page_size
        page_versions = sorted_versions[start_idx:end_idx]

        console.print(
            f"\n[cyan]Available versions (page {current_page + 1}, showing latest first):[/cyan]"
        )
        for idx, version in enumerate(page_versions, 1):
            build_count = len(versions[version])
            total_size = version_sizes[version]
            size_str = format_size(total_size) if total_size > 0 else "N/A"
            console.print(
                f"  {idx}. {version} ({build_count} build{'s' if build_count > 1 else ''}, {size_str})"
            )

        remaining = len(sorted_versions) - end_idx
        if remaining > 0:
            console.print(f"  [dim]... and {remaining} more versions[/dim]")

        # Allow typing version directly or selecting by number or showing more
        console.print("\n[dim]Options:[/dim]")
        console.print("  - Type a number (1-20) to select from the list")
        console.print("  - Type a version string directly (e.g., '1.26.4')")
        if remaining > 0:
            console.print("  - Type 'more' to see next page")
        if current_page > 0:
            console.print("  - Type 'back' to go to previous page")

        version_choice = Prompt.ask("\nEnter your choice")

        # Check if user wants more versions
        if version_choice.lower() == "more" and remaining > 0:
            current_page += 1
            continue
        elif version_choice.lower() == "back" and current_page > 0:
            current_page -= 1
            continue

        # Check if it's a number
        if version_choice.isdigit():
            choice_num = int(version_choice)
            if 1 <= choice_num <= len(page_versions):
                selected_version = page_versions[choice_num - 1]
                break
            else:
                console.print(
                    f"[red]Invalid choice. Please enter 1-{len(page_versions)}[/red]"
                )
                continue

        # Check if it's a direct version string
        if version_choice in versions:
            selected_version = version_choice
            break

        console.print(
            f"[red]Version '{version_choice}' not found. Please try again.[/red]"
        )

    console.print(f"\n[green]✓[/green] Selected version: {selected_version}")

    # Step 4: Display all builds
    console.print("\n[yellow]Step 4: Build Information[/yellow]\n")

    builds = versions[selected_version]

    # Create table
    table = Table(title=f"{selected_base}-{selected_version} Builds", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Build String", style="cyan")
    table.add_column("Full Package Name", style="white")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Timestamp", style="yellow")

    for idx, build_name in enumerate(sorted(builds), 1):
        info = matching_packages[build_name]
        size = info.get("size", "N/A")
        if isinstance(size, int):
            size_str = format_size(size)
        else:
            size_str = str(size)

        timestamp = info.get("timestamp", "N/A")
        if isinstance(timestamp, int):
            from datetime import datetime

            timestamp_str = datetime.fromtimestamp(timestamp / 1000).strftime(
                "%Y-%m-%d"
            )
        else:
            timestamp_str = str(timestamp)

        # Extract build string
        parts = build_name.rsplit("-", 2)
        build_string = parts[2] if len(parts) >= 3 else "unknown"

        table.add_row(str(idx), build_string, build_name, size_str, timestamp_str)

    console.print(table)

    # Ask which build to see PyPI mapping for
    console.print("\n[yellow]Step 5: View PyPI Mapping (optional)[/yellow]")
    console.print("\n[dim]Options:[/dim]")
    console.print("  - Type 'all' to see aggregated mapping across all builds")
    console.print("  - Type a build number to see mapping for specific build")
    console.print("  - Type 'n' to skip")

    mapping_choice = Prompt.ask("\nYour choice", default="all")

    if mapping_choice.lower() == "n":
        console.print("\n[dim]Skipping PyPI mapping view[/dim]")
        return

    # Try different backends to get artifact info
    backends = ["oci", "streamed", "libcfgraph"]

    if mapping_choice.lower() == "all":
        # Aggregate mappings across all builds
        console.print(
            f"\n[cyan]Fetching PyPI mappings for all {len(builds)} builds...[/cyan]\n"
        )

        all_mappings = []
        failed_builds = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[green]Fetching artifacts...", total=len(builds))

            for build_name in sorted(builds):
                artifact = None
                for backend in backends:
                    try:
                        artifact = get_artifact_info(
                            subdir=subdir,
                            artifact=build_name,
                            backend=backend,
                            channel=channel,
                        )
                        if artifact:
                            break
                    except Exception as e:
                        logger.debug(f"Backend {backend} failed for {build_name}: {e}")
                        continue

                if artifact:
                    mapping_entry = extract_artifact_mapping(artifact, build_name)
                    all_mappings.append((build_name, mapping_entry))
                else:
                    failed_builds.append(build_name)

                progress.advance(task)

        console.print(
            f"\n[green]✓[/green] Successfully fetched {len(all_mappings)}/{len(builds)} builds"
        )

        if failed_builds:
            console.print(
                f"[yellow]⚠[/yellow] Failed to fetch {len(failed_builds)} builds"
            )

        # Aggregate the data
        aggregated_pypi_packages: dict[
            str, dict[str, list[str]]
        ] = {}  # {pypi_name: {version: [build_names]}}
        aggregated_direct_urls: dict[str, list[str]] = {}  # {url: [build_names]}
        conda_package_name = None

        for build_name, mapping in all_mappings:
            if conda_package_name is None and mapping.conda_name:
                conda_package_name = mapping.conda_name

            if mapping.pypi_normalized_names and mapping.versions:
                for pypi_name in mapping.pypi_normalized_names:
                    if pypi_name not in aggregated_pypi_packages:
                        aggregated_pypi_packages[pypi_name] = {}

                    pypi_version: str | None = mapping.versions.get(pypi_name)
                    if pypi_version:
                        if pypi_version not in aggregated_pypi_packages[pypi_name]:
                            aggregated_pypi_packages[pypi_name][pypi_version] = []
                        # Extract just the build string
                        parts = build_name.rsplit("-", 2)
                        build_string = parts[2] if len(parts) >= 3 else build_name
                        aggregated_pypi_packages[pypi_name][pypi_version].append(
                            build_string
                        )

            if mapping.direct_url:
                for url in mapping.direct_url:
                    if url not in aggregated_direct_urls:
                        aggregated_direct_urls[url] = []
                    parts = build_name.rsplit("-", 2)
                    build_string = parts[2] if len(parts) >= 3 else build_name
                    aggregated_direct_urls[url].append(build_string)

        # Display aggregated results
        console.print(
            f"\n[bold cyan]📦 Aggregated PyPI Mapping for {selected_base}-{selected_version}:[/bold cyan]\n"
        )

        # Overview
        overview_table = Table(
            title="Overview", show_header=True, header_style="bold magenta"
        )
        overview_table.add_column("Field", style="cyan", width=20)
        overview_table.add_column("Value", style="white")

        overview_table.add_row("Conda Package", conda_package_name or "Unknown")
        overview_table.add_row("Version", selected_version)
        overview_table.add_row("Total Builds", str(len(builds)))
        overview_table.add_row(
            "PyPI Packages Found", str(len(aggregated_pypi_packages))
        )

        console.print(overview_table)

        # Create a single unified table with all PyPI mappings
        if aggregated_pypi_packages:
            console.print()
            mapping_table = Table(
                title="PyPI Package Mappings",
                show_header=True,
                header_style="bold magenta",
            )
            mapping_table.add_column("PyPI Package", style="cyan", no_wrap=True)
            mapping_table.add_column("Version", style="green", no_wrap=True)
            mapping_table.add_column("Conda Builds", style="white")

            # Flatten the nested structure into rows
            for pypi_name in sorted(aggregated_pypi_packages.keys()):
                versions = aggregated_pypi_packages[pypi_name]
                for version in sorted(versions.keys()):
                    build_strings = versions[version]

                    # Format builds display
                    if len(build_strings) <= 5:
                        builds_display = ", ".join(sorted(build_strings))
                    else:
                        builds_display = f"{', '.join(sorted(build_strings)[:5])}, ... (+{len(build_strings)-5} more)"

                    mapping_table.add_row(pypi_name, version, builds_display)

            console.print(mapping_table)

        # Direct URLs
        if aggregated_direct_urls:
            url_table = Table(
                title="Direct URLs (not on PyPI index)",
                show_header=True,
                header_style="bold magenta",
            )
            url_table.add_column("URL", style="blue")
            url_table.add_column("Builds", style="cyan")

            for url, build_strings in sorted(aggregated_direct_urls.items()):
                if len(build_strings) <= 3:
                    builds_display = ", ".join(sorted(build_strings))
                else:
                    builds_display = f"{', '.join(sorted(build_strings)[:3])}, ... (+{len(build_strings)-3} more)"

                url_table.add_row(url, builds_display)

            console.print(url_table)

        # Show note if no PyPI mappings found
        if not aggregated_pypi_packages and not aggregated_direct_urls:
            console.print(
                "\n[yellow]⚠ Note: No PyPI packages found in any of the builds[/yellow]"
            )

    else:
        # Single build view
        if not mapping_choice.isdigit() or not (
            1 <= int(mapping_choice) <= len(builds)
        ):
            console.print(
                f"[red]Invalid choice. Please select 1-{len(builds)} or 'all'[/red]"
            )
            return

        build_choice_idx = int(mapping_choice)
        selected_build = sorted(builds)[build_choice_idx - 1]

        console.print(f"\n[cyan]Fetching PyPI mapping for {selected_build}...[/cyan]")

        artifact = None

        with console.status("[bold green]Fetching artifact info..."):
            for backend in backends:
                try:
                    artifact = get_artifact_info(
                        subdir=subdir,
                        artifact=selected_build,
                        backend=backend,
                        channel=channel,
                    )
                    if artifact:
                        console.print(f"[dim]Using backend: {backend}[/dim]")
                        break
                except Exception as e:
                    logger.debug(f"Backend {backend} failed: {e}")
                    continue

        if artifact:
            mapping_entry = extract_artifact_mapping(artifact, selected_build)

            # Display mapping in a rich table
            console.print(
                f"\n[bold cyan]📦 PyPI Mapping for {selected_build}:[/bold cyan]\n"
            )

            # Create overview table
            overview_table = Table(
                title="Package Overview", show_header=True, header_style="bold magenta"
            )
            overview_table.add_column("Field", style="cyan", width=20)
            overview_table.add_column("Value", style="white")

            overview_table.add_row("Conda Package", mapping_entry.conda_name)
            overview_table.add_row("Package Filename", mapping_entry.package_name)
            overview_table.add_row(
                "PyPI Package(s)",
                ", ".join(mapping_entry.pypi_normalized_names)
                if mapping_entry.pypi_normalized_names
                else "None",
            )

            console.print(overview_table)

            # If there are PyPI packages, show version mapping
            if mapping_entry.pypi_normalized_names and mapping_entry.versions:
                console.print()
                versions_table = Table(
                    title="PyPI Version Mapping",
                    show_header=True,
                    header_style="bold magenta",
                )
                versions_table.add_column("PyPI Package", style="cyan")
                versions_table.add_column("Version", style="green")

                for pypi_name, version in mapping_entry.versions.items():
                    versions_table.add_row(pypi_name, version)

                console.print(versions_table)

            # If there are direct URLs, show them
            if mapping_entry.direct_url:
                console.print()
                url_table = Table(
                    title="Direct URLs (not on PyPI index)",
                    show_header=True,
                    header_style="bold magenta",
                )
                url_table.add_column("#", style="dim", width=4)
                url_table.add_column("URL", style="blue")

                for idx, url in enumerate(mapping_entry.direct_url, 1):
                    url_table.add_row(str(idx), url)

                console.print(url_table)

            # Show a note if no PyPI mapping was found
            if not mapping_entry.pypi_normalized_names:
                console.print(
                    "\n[yellow]⚠ Note: This package does not appear to contain any PyPI packages[/yellow]"
                )

        else:
            console.print("[red]✗[/red] Could not fetch artifact info from any backend")
