"""Rich table renderers used by the explorer flows."""

from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table
from rich.panel import Panel

from parselmouth.internals.channels import SupportedChannels
from parselmouth.internals.s3 import MappingEntry

from .common import console


@dataclass
class BuildTableRenderer:
    """Renders build information using Rich tables."""

    def render(self, package_name: str, version: str, builds: list[tuple[str, MappingEntry]]):
        table = Table(
            title=f"{package_name}-{version} Builds and PyPI Mappings",
            show_header=True,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Build String", style="cyan")
        table.add_column("Package Filename", style="white")
        table.add_column("PyPI Links", style="magenta", justify="right")
        table.add_column("PyPI Package(s)", style="green")
        table.add_column("PyPI Version(s)", style="yellow")

        for idx, (_, entry) in enumerate(sorted(builds, key=lambda x: x[1].package_name), 1):
            pkg_base = entry.package_name.replace(".tar.bz2", "").replace(".conda", "")
            parts = pkg_base.rsplit("-", 2)
            build_string = parts[2] if len(parts) >= 3 else "unknown"

            if entry.pypi_normalized_names:
                pypi_pkgs = ", ".join(entry.pypi_normalized_names[:3])
                if len(entry.pypi_normalized_names) > 3:
                    pypi_pkgs += f", ... (+{len(entry.pypi_normalized_names) - 3})"
                link_count = len(entry.pypi_normalized_names)
                row_style = "bright_white"
            else:
                pypi_pkgs = "[dim]None[/dim]"
                link_count = 0
                row_style = "dim"

            if entry.versions:
                version_values = list(entry.versions.values())
                pypi_versions = ", ".join(f"{v}" for v in version_values[:3])
                if len(version_values) > 3:
                    pypi_versions += f", ... (+{len(version_values) - 3})"
            else:
                pypi_versions = "[dim]N/A[/dim]"

            table.add_row(
                str(idx),
                build_string,
                entry.package_name,
                str(link_count),
                pypi_pkgs,
                pypi_versions,
                style=row_style,
            )

        console.print(table)


@dataclass
class PyPIVersionTableRenderer:
    """Handles presentation of PyPI lookup results."""

    def render_overview(
        self,
        normalized_name: str,
        channel: SupportedChannels,
        sorted_versions: list[tuple[str, list[str]]],
    ):
        table = Table(
            title=f"PyPI Package: {normalized_name} (Channel: {channel})",
            show_header=True,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("PyPI Version", style="green")
        table.add_column("Conda Packages", style="cyan")
        table.add_column("Conda Count", style="magenta", justify="right")

        for idx, (pypi_version, conda_packages) in enumerate(sorted_versions, 1):
            if len(conda_packages) <= 3:
                packages_str = ", ".join(conda_packages)
            else:
                packages_str = f"{', '.join(conda_packages[:3])}, ... (+{len(conda_packages)-3} more)"

            count = len(conda_packages)

            table.add_row(
                str(idx),
                pypi_version,
                packages_str,
                str(count),
            )

        console.print(table)

    def render_detail(
        self,
        pypi_name: str,
        pypi_version: str,
        conda_packages: list[str],
        channel: SupportedChannels,
    ):
        console.print(
            Panel.fit(
                f"[cyan]PyPI:[/cyan] {pypi_name}\n[cyan]Version:[/cyan] {pypi_version}\n[cyan]Channel:[/cyan] {channel}",
                title="PyPI Selection",
                border_style="green",
            )
        )

        table = Table(title=f"Conda Packages (Channel: {channel})", show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Conda Package Name", style="cyan")

        for idx, conda_pkg in enumerate(conda_packages, 1):
            table.add_row(str(idx), conda_pkg)

        console.print(table)
        console.print(
            f"\n[green]✓[/green] {len(conda_packages)} conda package(s) provide {pypi_name}=={pypi_version}"
        )
        console.print(
            "\n[dim]Note: To view build details (size, timestamp, etc.), you need the package hash.[/dim]"
        )
        console.print("[dim]Hash lookups can be added here in a future enhancement.[/dim]")


__all__ = ["BuildTableRenderer", "PyPIVersionTableRenderer"]
