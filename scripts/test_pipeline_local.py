#!/usr/bin/env python3
"""
Test the complete parselmouth pipeline locally with MinIO.

This script:
1. Connects to local MinIO instance (started via docker-compose)
2. Runs the updater-producer to find new packages
3. Processes packages through the updater
4. Merges partial indices
5. Generates v1 relations table and PyPI lookups
6. Verifies all data is accessible

Usage:
    # Start MinIO first
    docker-compose up -d

    # Run the pipeline (defaults: pytorch, noarch, letter 't')
    python scripts/test_pipeline_local.py

    # Use different channel, subdir, and letter
    python scripts/test_pipeline_local.py --channel conda-forge --subdir linux-64 --letter p

    # Interactive mode (recommended)
    python scripts/test_pipeline_local.py --interactive

    # Access MinIO UI at http://localhost:9001
    # Login: minioadmin / minioadmin
"""

import os
import sys
import logging
import time
from datetime import datetime
from pathlib import Path
import argparse

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich import box

console = Console()

# Setup environment for MinIO
os.environ["R2_PREFIX_ACCESS_KEY_ID"] = "minioadmin"
os.environ["R2_PREFIX_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["R2_PREFIX_BUCKET"] = "conda"

# Point to local MinIO instead of Cloudflare R2
os.environ["R2_PREFIX_ENDPOINT"] = "http://localhost:9000"

from parselmouth.internals.channels import SupportedChannels  # noqa: E402
from parselmouth.internals.updater_producer import main as producer_main  # noqa: E402
from parselmouth.internals.updater import main as updater_main  # noqa: E402
from parselmouth.internals.updater_merger import main as merger_main  # noqa: E402
from parselmouth.internals.relations_updater import main as relations_main  # noqa: E402
from parselmouth.internals.s3 import s3_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Filter out YAML parsing errors from conda-forge-metadata (external library)
# These are often due to malformed package metadata and are already handled gracefully
class YAMLErrorFilter(logging.Filter):
    def filter(self, record):
        # Suppress "while scanning for the next token" YAML errors from root logger
        if (
            record.name == "root"
            and "while scanning for the next token" in record.getMessage()
        ):
            return False
        return True


# Apply filter to root logger to suppress external library YAML errors
logging.getLogger().addFilter(YAMLErrorFilter())


def wait_for_minio(max_retries=30):
    """Wait for MinIO to be ready."""
    import boto3

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Waiting for MinIO to be ready...", total=None)

        for i in range(max_retries):
            try:
                # Try to list buckets
                client = boto3.client(
                    "s3",
                    endpoint_url="http://localhost:9000",
                    aws_access_key_id="minioadmin",
                    aws_secret_access_key="minioadmin",
                )
                client.list_buckets()
                progress.update(task, description="[green]✓ MinIO is ready!")
                return True
            except Exception as e:
                if i < max_retries - 1:
                    progress.update(
                        task, description=f"Waiting for MinIO... ({i+1}/{max_retries})"
                    )
                    time.sleep(2)
                else:
                    progress.update(task, description="[red]✗ MinIO failed to start")
                    console.print(f"[red]Error: {e}")
                    return False
    return False


def format_duration(seconds):
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def show_minio_statistics():
    """Display current MinIO statistics."""
    console.print()
    console.rule("[bold cyan]MinIO Statistics", style="cyan")
    console.print()

    stats_table = Table(
        title="📊 Current Storage Status",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    stats_table.add_column("Channel", style="cyan", width=15)
    stats_table.add_column("Packages", justify="right", style="magenta")
    stats_table.add_column("With PyPI", justify="right", style="green")
    stats_table.add_column("Relations", justify="center", style="yellow")
    stats_table.add_column("PyPI Lookups", justify="right", style="blue")

    # Check each supported channel
    for channel_name in [c.value for c in SupportedChannels]:
        try:
            channel = SupportedChannels(channel_name)

            # Get index
            try:
                index = s3_client.get_channel_index(channel)
                if index:
                    total_packages = len(index.root)
                    with_pypi = sum(
                        1
                        for entry in index.root.values()
                        if entry.pypi_normalized_names
                        and len(entry.pypi_normalized_names) > 0
                    )
                else:
                    total_packages = 0
                    with_pypi = 0
            except Exception:
                total_packages = 0
                with_pypi = 0

            # Check relations table
            try:
                table_data = s3_client.get_relations_table(channel)
                has_relations = "✓" if table_data else "✗"
            except Exception:
                has_relations = "✗"

            # Count PyPI lookup files
            try:
                lookup_files = s3_client.list_pypi_lookup_files(channel)
                lookup_count = len(lookup_files)
            except Exception:
                lookup_count = 0

            # Add row
            stats_table.add_row(
                channel_name,
                f"{total_packages:,}" if total_packages > 0 else "-",
                f"{with_pypi:,}" if with_pypi > 0 else "-",
                has_relations,
                f"{lookup_count:,}" if lookup_count > 0 else "-",
            )
        except Exception as e:
            logger.debug(f"Error getting stats for {channel_name}: {e}")
            stats_table.add_row(channel_name, "-", "-", "✗", "-")

    console.print(stats_table)
    console.print()


def interactive_prompts():
    """Run interactive prompts to gather user input."""
    console.print("[bold cyan]Interactive Mode[/bold cyan]")
    console.print("[dim]Answer the questions below to configure your test run[/dim]")
    console.print()

    # Channel selection
    channel = Prompt.ask(
        "Which channel do you want to test?",
        choices=["conda-forge", "pytorch", "bioconda"],
        default="pytorch",
    )

    # Subdir selection
    console.print()
    console.print(
        "[dim]Common subdirs: noarch, linux-64, osx-64, osx-arm64, win-64[/dim]"
    )
    subdir = Prompt.ask(
        "Which subdir do you want to process?",
        default="noarch",
    )

    # Letter selection
    console.print()
    console.print(
        "[dim]Filter packages by first letter of package name (e.g., 'n' for numpy, napari)[/dim]"
    )
    console.print("[dim]Or use 'all' to process all packages in the subdir[/dim]")
    letter = Prompt.ask(
        "Which letter to filter by?",
        default="t",
    ).lower()

    # Mode selection
    console.print()
    console.print("[dim]Fresh mode: reprocess all packages (slower, complete)[/dim]")
    console.print(
        "[dim]Incremental mode: skip packages already in MinIO (faster)[/dim]"
    )
    mode = Prompt.ask(
        "Which processing mode?",
        choices=["fresh", "incremental"],
        default="fresh",
    )

    console.print()

    return channel, subdir, letter, mode


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Test parselmouth pipeline locally with MinIO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended for new users)
  python scripts/test_pipeline_local.py --interactive

  # Quick start with defaults (pytorch, noarch, letter 't', fresh mode)
  python scripts/test_pipeline_local.py

  # Test with conda-forge, only package names starting with 'p'
  python scripts/test_pipeline_local.py --channel conda-forge --letter p

  # Test incrementally (skip existing packages)
  python scripts/test_pipeline_local.py --mode incremental

  # Test with bioconda, process ALL packages in linux-64
  python scripts/test_pipeline_local.py --channel bioconda --subdir linux-64 --letter all
        """,
    )

    parser.add_argument(
        "--channel",
        type=str,
        default="pytorch",
        choices=["conda-forge", "pytorch", "bioconda"],
        help="Channel to test (default: pytorch)",
    )

    parser.add_argument(
        "--subdir",
        type=str,
        default="noarch",
        help="Subdir to process (default: noarch). Examples: noarch, linux-64, osx-arm64",
    )

    parser.add_argument(
        "--letter",
        type=str,
        default="t",
        help="Letter to filter package NAMES by first character (default: t). Use 'all' to process all packages in subdir. Example: 'n' processes numpy, napari, etc.",
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="fresh",
        choices=["fresh", "incremental"],
        help="Processing mode: 'fresh' reprocesses everything, 'incremental' skips existing packages (default: fresh)",
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode: prompt for all settings and show MinIO statistics",
    )

    return parser.parse_args()


def main():
    """Run the complete pipeline."""

    args = parse_args()

    # Wait for MinIO first (before showing stats)
    if not wait_for_minio():
        console.print("[red]✗ MinIO is not available. Please run: docker-compose up -d")
        sys.exit(1)

    # Interactive mode
    if args.interactive:
        show_minio_statistics()
        channel_str, subdir, letter, mode = interactive_prompts()
        channel = SupportedChannels(channel_str)
    else:
        # Use command-line arguments
        channel = SupportedChannels(args.channel)
        subdir = args.subdir
        letter = args.letter
        mode = args.mode

    start_time = time.time()

    # Build subdir_letter for processing
    subdir_letter = f"{subdir}@{letter}"

    # Determine processing mode
    check_if_exists = mode == "incremental"
    mode_desc = (
        "incremental (skip existing)" if check_if_exists else "fresh (reprocess all)"
    )

    # Build display description
    if letter.lower() == "all":
        filter_desc = "ALL packages"
    else:
        filter_desc = f"package names starting with '{letter}'"

    # Print header
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]PARSELMOUTH LOCAL PIPELINE TEST[/bold cyan]\n\n"
            f"[dim]Channel:[/dim] {channel.value}\n"
            f"[dim]Subdir:[/dim] {subdir}\n"
            f"[dim]Filter:[/dim] {filter_desc}\n"
            f"[dim]Mode:[/dim] {mode_desc}\n"
            f"[dim]MinIO Endpoint:[/dim] {os.environ['R2_PREFIX_ENDPOINT']}\n"
            f"[dim]Bucket:[/dim] {os.environ['R2_PREFIX_BUCKET']}\n"
            f"[dim]Started:[/dim] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )
    console.print()

    # Track step timings
    step_times = {}
    step_status = {}

    # Create output directories
    output_dir = Path("./local_test_output")
    output_dir.mkdir(exist_ok=True)

    partial_output = output_dir / "partial"
    partial_output.mkdir(exist_ok=True)

    relations_output = output_dir / "relations"
    relations_output.mkdir(exist_ok=True)

    # ========================================================================
    # STEP 1: Producer - Find new packages
    # ========================================================================
    console.rule("[bold blue]Step 1/5: Updater Producer", style="blue")
    console.print("[dim]Finding new packages that need processing...[/dim]")
    step_start = time.time()

    try:
        producer_main(
            output_dir=str(output_dir / "index"),
            check_if_exists=check_if_exists,
            check_if_pypi_exists=False,
            channel=channel,
            subdir=subdir,
        )
        step_times["producer"] = time.time() - step_start
        step_status["producer"] = "success"
        console.print(
            f"[green]✓ Producer completed in {format_duration(step_times['producer'])}[/green]"
        )
    except Exception as e:
        step_times["producer"] = time.time() - step_start
        step_status["producer"] = "warning"
        console.print(f"[yellow]⚠ Producer warning: {e}[/yellow]")
        # Continue anyway - might be no new packages

    console.print()

    # ========================================================================
    # STEP 2: Updater - Process packages
    # ========================================================================
    console.rule("[bold blue]Step 2/5: Updater", style="blue")
    console.print("[dim]Processing packages and uploading to MinIO (hash-v0/)...[/dim]")
    console.print(f"[dim]Processing '{subdir_letter}' from {channel.value}[/dim]")
    console.print(
        "[dim]Note: Some packages may fail due to malformed metadata (this is normal)[/dim]"
    )
    step_start = time.time()

    try:
        updater_main(
            subdir_letter=subdir_letter,
            output_dir=str(output_dir / "index"),
            partial_output_dir=str(partial_output),
            channel=channel,
            upload=True,
        )
        step_times["updater"] = time.time() - step_start
        step_status["updater"] = "success"
        console.print(
            f"[green]✓ Updater completed for {subdir_letter} in {format_duration(step_times['updater'])}[/green]"
        )
        console.print(
            "[dim]   Check logs above for any 'Could not get artifact' warnings[/dim]"
        )
    except Exception as e:
        step_times["updater"] = time.time() - step_start
        step_status["updater"] = "warning"
        console.print(f"[yellow]⚠ Updater warning: {e}[/yellow]")

    console.print()

    # ========================================================================
    # STEP 3: Merger - Combine partial indices
    # ========================================================================
    console.rule("[bold blue]Step 3/5: Merger", style="blue")
    console.print("[dim]Merging partial indices into master index...[/dim]")
    step_start = time.time()

    try:
        merger_main(
            output_dir=str(partial_output),
            channel=channel,
            upload=True,
        )
        step_times["merger"] = time.time() - step_start
        step_status["merger"] = "success"
        console.print(
            f"[green]✓ Merger completed in {format_duration(step_times['merger'])}[/green]"
        )
    except Exception as e:
        step_times["merger"] = time.time() - step_start
        step_status["merger"] = "error"
        console.print(f"[red]✗ Merger failed: {e}[/red]")

    console.print()

    # ========================================================================
    # STEP 4: Relations - Generate v1 mappings
    # ========================================================================
    console.rule("[bold blue]Step 4/5: Relations Updater", style="blue")
    console.print("[dim]Generating v1 relations table and PyPI lookups...[/dim]")
    step_start = time.time()

    try:
        relations_main(
            channel=channel,
            upload=True,
            output_dir=str(relations_output),
            skip_unchanged=True,
            public_url=False,
        )
        step_times["relations"] = time.time() - step_start
        step_status["relations"] = "success"
        console.print(
            f"[green]✓ Relations updater completed in {format_duration(step_times['relations'])}[/green]"
        )
    except Exception as e:
        step_times["relations"] = time.time() - step_start
        step_status["relations"] = "error"
        console.print(f"[red]✗ Relations updater failed: {e}[/red]")

    console.print()

    # ========================================================================
    # STEP 5: Verification
    # ========================================================================
    console.rule("[bold blue]Step 5/5: Verification", style="blue")
    step_start = time.time()

    verification_results = []
    packages_with_pypi = 0
    packages_without_pypi = 0

    try:
        index = s3_client.get_channel_index(channel)
        if index:
            # Count packages with/without PyPI metadata
            for hash_val, entry in index.root.items():
                if entry.pypi_normalized_names and len(entry.pypi_normalized_names) > 0:
                    packages_with_pypi += 1
                else:
                    packages_without_pypi += 1

            verification_results.append(
                ("[green]✓[/green]", f"Index found with {len(index.root):,} packages")
            )
            if packages_with_pypi > 0:
                verification_results.append(
                    (
                        "[green]✓[/green]",
                        f"  ├─ {packages_with_pypi} packages WITH PyPI metadata",
                    )
                )
            if packages_without_pypi > 0:
                verification_results.append(
                    (
                        "[yellow]⚠[/yellow]",
                        f"  └─ {packages_without_pypi} packages WITHOUT PyPI metadata",
                    )
                )
        else:
            verification_results.append(("[yellow]⚠[/yellow]", "No index found"))

        try:
            table_data = s3_client.get_relations_table(channel)
            size_mb = len(table_data) / 1024 / 1024
            verification_results.append(
                (
                    "[green]✓[/green]",
                    f"Relations table found ({size_mb:.1f} MB compressed)",
                )
            )
        except Exception:
            verification_results.append(
                ("[yellow]⚠[/yellow]", "No relations table found")
            )

        # Check if any PyPI lookup files exist
        try:
            lookup_files = s3_client.list_pypi_lookup_files(channel)
            if lookup_files:
                # Show a sample file if available
                sample_file = next(iter(lookup_files))
                verification_results.append(
                    (
                        "[green]✓[/green]",
                        f"PyPI lookup files exist ({len(lookup_files)} files, e.g. '{sample_file}')",
                    )
                )
            else:
                verification_results.append(
                    ("[yellow]⚠[/yellow]", "No PyPI lookup files found")
                )
        except Exception as e:
            verification_results.append(
                ("[yellow]⚠[/yellow]", f"Could not check PyPI lookups: {e}")
            )

    except Exception as e:
        verification_results.append(("[red]✗[/red]", f"Verification error: {e}"))
        step_status["verification"] = "error"

    step_times["verification"] = time.time() - step_start
    step_status["verification"] = step_status.get("verification", "success")

    for icon, result in verification_results:
        console.print(f"{icon} {result}")

    # Show sample package if available
    if index and len(index.root) > 0:
        console.print()
        console.print("[dim]Sample package from index:[/dim]")
        sample_hash, sample_entry = list(index.root.items())[0]
        console.print(f"[dim]  Hash: {sample_hash[:16]}...[/dim]")
        console.print(f"[dim]  Package: {sample_entry.package_name}[/dim]")
        console.print(f"[dim]  PyPI names: {sample_entry.pypi_normalized_names}[/dim]")

    console.print()

    # ========================================================================
    # Summary
    # ========================================================================
    total_time = time.time() - start_time

    console.rule("[bold green]Pipeline Complete!", style="green")
    console.print()

    # Create timing table
    timing_table = Table(
        title="⏱️  Timing Summary",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    timing_table.add_column("Step", style="cyan", width=20)
    timing_table.add_column("Duration", justify="right", style="magenta")
    timing_table.add_column("Status", justify="center")

    status_icons = {
        "success": "[green]✓[/green]",
        "warning": "[yellow]⚠[/yellow]",
        "error": "[red]✗[/red]",
    }

    for step, duration in step_times.items():
        status = step_status.get(step, "success")
        timing_table.add_row(
            step.capitalize(), format_duration(duration), status_icons[status]
        )

    timing_table.add_section()
    timing_table.add_row(
        "[bold]Total[/bold]", f"[bold]{format_duration(total_time)}[/bold]", ""
    )

    console.print(timing_table)
    console.print()

    # Access info panel
    info_panel = Panel(
        "[bold cyan]Access MinIO UI[/bold cyan]\n\n"
        "[dim]URL:[/dim]      http://localhost:9001\n"
        "[dim]Username:[/dim] minioadmin\n"
        "[dim]Password:[/dim] minioadmin\n\n"
        f"[bold cyan]Local Output[/bold cyan]\n\n"
        f"[dim]{output_dir}[/dim]\n\n"
        "[bold cyan]Clean Up[/bold cyan]\n\n"
        "[dim]pixi run clean-all[/dim]         (everything + MinIO)\n"
        "[dim]pixi run clean-local-data[/dim]  (cache + outputs)\n"
        "[dim]pixi run clean-cache[/dim]       (conda cache only)\n"
        "[dim]pixi run clean-outputs[/dim]     (outputs only)",
        border_style="green",
        box=box.ROUNDED,
    )
    console.print(info_panel)
    console.print()


if __name__ == "__main__":
    main()
