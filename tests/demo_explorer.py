"""
Demo script showing the Conda -> PyPI package explorer functionality.

To actually use the interactive explorer, run:
    pixi run parselmouth explore

This script demonstrates the data flow without interactive prompts.
"""

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.conda_forge import get_all_packages_by_subdir
from rich.console import Console
from rich.table import Table

console = Console()

def demo_package_data():
    """
    Demonstrate fetching and displaying Conda -> PyPI package data.
    """
    console.print("\n[bold cyan]🔍 Conda → PyPI Package Explorer Demo[/bold cyan]\n")

    # Step 1: Fetch data for a subdir
    subdir = "noarch"
    console.print(f"[yellow]Fetching packages from {subdir}...[/yellow]")

    with console.status("[bold green]Loading repodata..."):
        repodatas = get_all_packages_by_subdir(subdir, SupportedChannels.CONDA_FORGE)

    # Flatten all packages
    all_packages = {}
    for label, packages in repodatas.items():
        all_packages.update(packages)

    console.print(f"[green]✓[/green] Loaded {len(all_packages)} packages\n")

    # Step 2: Find a specific package (e.g., requests)
    package_name = "requests"
    matching = {
        name: info for name, info in all_packages.items()
        if name.startswith(package_name + "-")
    }

    console.print(f"[cyan]Found {len(matching)} builds of '{package_name}'[/cyan]\n")

    # Step 3: Group by version
    versions = {}
    for full_name in matching.keys():
        parts = full_name.rsplit('-', 2)
        if len(parts) >= 3:
            version = parts[1]
            if version not in versions:
                versions[version] = []
            versions[version].append(full_name)

    # Step 4: Show a table for one version
    if versions:
        # Pick the first version
        sample_version = sorted(versions.keys(), reverse=True)[0]
        builds = versions[sample_version]

        console.print(f"[yellow]Showing builds for version {sample_version}:[/yellow]\n")

        table = Table(title=f"{package_name}-{sample_version} Builds", show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Build String", style="cyan")
        table.add_column("Full Package Name", style="white")
        table.add_column("Size", justify="right", style="green")

        for idx, build_name in enumerate(sorted(builds)[:10], 1):  # Show first 10
            info = matching[build_name]
            size = info.get('size', 'N/A')
            if isinstance(size, int):
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
            else:
                size_str = str(size)

            parts = build_name.rsplit('-', 2)
            build_string = parts[2] if len(parts) >= 3 else "unknown"

            table.add_row(
                str(idx),
                build_string,
                build_name,
                size_str
            )

        console.print(table)
        console.print(f"\n[dim]... and {len(builds) - 10} more builds[/dim]" if len(builds) > 10 else "")

    console.print("\n[green]✓[/green] Demo complete!\n")
    console.print("[cyan]To use the interactive explorer, run:[/cyan]")
    console.print("    [bold]pixi run parselmouth explore[/bold]\n")


if __name__ == "__main__":
    demo_package_data()
