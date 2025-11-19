"""Interactive selector components used by the explorer flows."""

from __future__ import annotations

from dataclasses import dataclass

from rich.prompt import Prompt
from rich.table import Table

from parselmouth.internals.channels import SupportedChannels

from .catalog import PackageCatalog, PackageVersions
from .common import console, PRODUCTION_URL, LOCAL_MINIO_URL


@dataclass
class EndpointSelector:
    """Component responsible for resolving which endpoint to use."""

    def resolve(self, base_url: str | None = None) -> str:
        if base_url:
            return base_url

        console.print("\n[yellow]Select Endpoint[/yellow]")
        console.print(f"1. Production ({PRODUCTION_URL})")
        console.print(f"2. Local MinIO ({LOCAL_MINIO_URL})")

        choice = Prompt.ask("\nSelect endpoint", choices=["1", "2"], default="1")

        if choice == "1":
            console.print("[green]✓[/green] Using production endpoint")
            return PRODUCTION_URL
        console.print("[green]✓[/green] Using local MinIO endpoint")
        return LOCAL_MINIO_URL


@dataclass
class ChannelSelector:
    """Interactive selector for SupportedChannels."""

    def resolve(self, channel: SupportedChannels | None = None) -> SupportedChannels:
        if channel is not None:
            return channel

        console.print("\n[yellow]Select Channel[/yellow]")
        console.print("1. conda-forge")
        console.print("2. pytorch")
        console.print("3. bioconda")

        choice = Prompt.ask("\nSelect channel", choices=["1", "2", "3"], default="1")

        if choice == "1":
            return SupportedChannels.CONDA_FORGE
        if choice == "2":
            return SupportedChannels.PYTORCH
        return SupportedChannels.BIOCONDA


@dataclass
class CondaPackageSelector:
    """Interactive selection of conda package names."""

    catalog: PackageCatalog

    def select(self, package_name: str | None, prompt_on_multiple: bool = True) -> tuple[str, PackageVersions]:
        if package_name is None:
            console.print("[yellow]Enter Package Name[/yellow]")
            console.print("[dim]Tip: Enter a partial name to search[/dim]")
            package_name = Prompt.ask("\nPackage name")

        matching_packages = self.catalog.search(package_name)

        if not matching_packages:
            console.print(f"[red]✗[/red] No packages found matching '{package_name}'")
            console.print("\n[dim]Some available packages:[/dim]")
            for suggestion in self.catalog.suggestions():
                console.print(f"  - {suggestion}")
            raise ValueError("Package not found")

        if len(matching_packages) > 50:
            console.print(
                f"[yellow]⚠[/yellow] Found {len(matching_packages)} matching packages. Showing first 50."
            )
            console.print("[dim]Be more specific to narrow down results.[/dim]\n")
            matching_packages = dict(list(matching_packages.items())[:50])

        if len(matching_packages) > 1 and prompt_on_multiple:
            console.print("\n[cyan]Found multiple packages:[/cyan]")
            pkg_list = sorted(matching_packages.keys())
            table = Table(show_header=True, title="Matching Packages")
            table.add_column("#", style="dim", width=4)
            table.add_column("Package Name", style="cyan")
            table.add_column("Versions", style="green", justify="right")

            for idx, name in enumerate(pkg_list[:20], 1):
                version_count = len(matching_packages[name])
                suffix = "s" if version_count != 1 else ""
                table.add_row(str(idx), name, f"{version_count} version{suffix}")

            console.print(table)

            if len(pkg_list) > 20:
                console.print(f"[dim]... and {len(pkg_list) - 20} more[/dim]")

            choice = Prompt.ask(
                "\nSelect package number",
                choices=[str(i) for i in range(1, min(len(pkg_list), 20) + 1)],
                default="1",
            )
            selected_package = pkg_list[int(choice) - 1]
        else:
            selected_package = next(iter(matching_packages))

        return selected_package, matching_packages[selected_package]


def _version_sort_key(version_str: str):
    from packaging.version import InvalidVersion, Version

    try:
        return Version(version_str)
    except InvalidVersion:
        return version_str


@dataclass
class VersionSelector:
    """Interactive selector for package versions."""

    def select(self, versions_dict: PackageVersions, requested: str | None) -> str | None:
        if requested:
            if requested in versions_dict:
                return requested
            console.print(f"[red]Version '{requested}' not found[/red]")
            return None

        console.print("[yellow]Available Versions[/yellow]")
        sorted_versions = sorted(
            versions_dict.keys(), key=lambda v: _version_sort_key(v), reverse=True
        )

        for idx, ver in enumerate(sorted_versions[:30], 1):
            build_count = len(versions_dict[ver])
            suffix = "s" if build_count > 1 else ""
            console.print(f"  {idx}. {ver} ({build_count} build{suffix})")

        if len(sorted_versions) > 30:
            console.print(f"  [dim]... and {len(sorted_versions) - 30} more versions[/dim]")

        version_choice = Prompt.ask("\nEnter version number or version string", default="1")

        if version_choice.isdigit():
            choice_num = int(version_choice)
            if 1 <= choice_num <= min(len(sorted_versions), 30):
                return sorted_versions[choice_num - 1]
            console.print("[red]Invalid choice[/red]")
            return None

        if version_choice in versions_dict:
            return version_choice

        console.print(f"[red]Version '{version_choice}' not found[/red]")
        return None


__all__ = [
    "EndpointSelector",
    "ChannelSelector",
    "CondaPackageSelector",
    "VersionSelector",
]
