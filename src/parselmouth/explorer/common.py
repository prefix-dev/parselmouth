"""Shared state and constants for the explorer modules."""

from __future__ import annotations

import logging

from rich.console import Console


console = Console()
logger = logging.getLogger(__name__)

# Endpoint URLs used by the interactive prompts
PRODUCTION_URL = "https://conda-mapping.prefix.dev"
LOCAL_MINIO_URL = "http://localhost:9000/conda"


__all__ = [
    "console",
    "logger",
    "PRODUCTION_URL",
    "LOCAL_MINIO_URL",
]
