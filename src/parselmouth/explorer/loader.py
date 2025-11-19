"""Helpers responsible for downloading cached channel indices."""

from __future__ import annotations

from dataclasses import dataclass

from parselmouth.internals.channels import SupportedChannels
from .index_cache import fetch_channel_index_cached
from parselmouth.internals.s3 import IndexMapping

from .common import console


@dataclass
class PackageIndexLoader:
    """Handles downloading and caching the channel index."""

    channel: SupportedChannels
    base_url: str

    def load(self) -> tuple[IndexMapping | None, str | None]:
        with console.status("[bold green]Checking for updates...") as status:
            def progress_callback(message: str):
                status.update(f"[bold green]{message}")

            index, cache_status = fetch_channel_index_cached(
                self.channel,
                self.base_url,
                progress_callback=progress_callback,
            )

        if not index:
            console.print("[red]✗[/red] Failed to fetch channel index")
            console.print(
                "[dim]Make sure the endpoint is accessible and contains data for this channel.[/dim]"
            )
            return None, None

        console.print(
            f"[green]✓[/green] Loaded {len(index.root)} package mappings [dim]({cache_status})[/dim]\n"
        )
        return index, cache_status


__all__ = ["PackageIndexLoader"]
