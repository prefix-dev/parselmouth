"""
Demo script showing the HTTP-based Conda <-> PyPI package explorer functionality.

This demonstrates both:
1. Conda -> PyPI explorer (currently simplified)
2. PyPI -> Conda explorer (fully functional)

To use the interactive explorers, run:
    pixi run parselmouth explore-pypi              # PyPI -> Conda (interactive)
    pixi run parselmouth explore                   # Conda -> PyPI (interactive)

This script demonstrates non-interactive usage for testing.
"""

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.package_explorer import explore_pypi_package
from parselmouth.internals.mapping_http_client import fetch_pypi_lookup
from rich.console import Console
from rich.table import Table

console = Console()

# Endpoint URLs
LOCAL_MINIO = "http://localhost:9000/conda"
PRODUCTION = "https://conda-mapping.prefix.dev"


def demo_pypi_to_conda_http():
    """
    Demonstrate PyPI -> Conda lookups via HTTP.

    This is the main explorer that works with HTTP endpoints.
    """
    console.print("\n[bold cyan]🔍 PyPI → Conda Explorer Demo (HTTP)[/bold cyan]\n")
    console.print("[yellow]Testing PyPI -> Conda lookup via HTTP...[/yellow]\n")

    # Example 1: Look up 'requests' in conda-forge
    pypi_name = "requests"
    channel = SupportedChannels.CONDA_FORGE

    console.print(f"[cyan]Looking up '{pypi_name}' in {channel}...[/cyan]")

    # Try production endpoint
    console.print(f"[dim]Using endpoint: {PRODUCTION}[/dim]\n")

    with console.status("[bold green]Fetching PyPI -> Conda mappings..."):
        lookup = fetch_pypi_lookup(channel, pypi_name, base_url=PRODUCTION)

    if lookup:
        console.print(f"[green]✓[/green] Found {len(lookup.conda_versions)} PyPI versions\n")

        # Show a sample of versions
        table = Table(
            title=f"Sample Versions for {pypi_name}",
            show_header=True,
        )
        table.add_column("PyPI Version", style="green")
        table.add_column("Conda Packages", style="cyan")

        # Show first 10 versions
        versions = sorted(lookup.conda_versions.keys(), reverse=True)[:10]
        for version in versions:
            conda_pkgs = lookup.conda_versions[version]
            if len(conda_pkgs) <= 3:
                pkgs_str = ", ".join(conda_pkgs)
            else:
                pkgs_str = f"{', '.join(conda_pkgs[:3])}, ... (+{len(conda_pkgs)-3} more)"

            table.add_row(version, pkgs_str)

        console.print(table)

        if len(lookup.conda_versions) > 10:
            console.print(f"\n[dim]... and {len(lookup.conda_versions) - 10} more versions[/dim]")
    else:
        console.print(f"[red]✗[/red] No mappings found for '{pypi_name}'")

    console.print("\n[green]✓[/green] Demo complete!\n")


def demo_non_interactive_usage():
    """
    Demonstrate non-interactive usage for automated testing.
    """
    console.print("\n[bold cyan]📋 Non-Interactive Usage Examples[/bold cyan]\n")

    console.print("[yellow]Example 1: PyPI -> Conda with all parameters[/yellow]")
    console.print("[dim]Command:[/dim]")
    console.print("  parselmouth explore-pypi --endpoint production --channel conda-forge --pypi-name numpy\n")

    console.print("[yellow]Example 2: View specific version[/yellow]")
    console.print("[dim]Command:[/dim]")
    console.print("  parselmouth explore-pypi --endpoint local --channel conda-forge --pypi-name requests --version 2.31.0\n")

    console.print("[yellow]Example 3: Using local MinIO[/yellow]")
    console.print("[dim]Prerequisites:[/dim]")
    console.print("  1. Start MinIO: docker-compose up -d")
    console.print("  2. Run test pipeline: pixi run test-pipeline")
    console.print("[dim]Command:[/dim]")
    console.print("  parselmouth explore-pypi --endpoint local --channel pytorch --pypi-name torch\n")


def demo_interactive_help():
    """
    Show how to use the interactive explorers.
    """
    console.print("\n[bold cyan]💡 Interactive Explorer Usage[/bold cyan]\n")

    console.print("[yellow]PyPI → Conda Explorer (Recommended)[/yellow]")
    console.print("This explorer is fully functional with HTTP endpoints:\n")
    console.print("  [bold]pixi run parselmouth explore-pypi[/bold]")
    console.print("  [dim]or[/dim]")
    console.print("  [bold]pixi run parselmouth explore-pypi --endpoint local[/bold]\n")

    console.print("[yellow]Conda → PyPI Explorer[/yellow]")
    console.print("Currently simplified - requires full index support:\n")
    console.print("  [bold]pixi run parselmouth explore[/bold]")
    console.print("  [dim](Note: Full browsing not yet implemented for HTTP-only mode)[/dim]\n")


def main():
    """
    Run all demos.
    """
    console.print("\n" + "="*70)
    console.print("[bold]Parselmouth HTTP-Based Explorer Demos[/bold]")
    console.print("="*70)

    # Demo 1: PyPI -> Conda HTTP lookups
    demo_pypi_to_conda_http()

    # Demo 2: Non-interactive usage
    demo_non_interactive_usage()

    # Demo 3: Interactive help
    demo_interactive_help()

    console.print("\n[cyan]For more information, see:[/cyan]")
    console.print("  - README.md")
    console.print("  - docs/LOCAL_TESTING.md")
    console.print()


if __name__ == "__main__":
    main()
