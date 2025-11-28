"""HTTP utilities with optimized connection pooling for parallel requests."""

import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session_with_large_pool(
    pool_connections: int = 100,
    pool_maxsize: int = 100,
    max_retries: int = 3,
) -> requests.Session:
    """
    Create a requests Session with a larger connection pool.

    This prevents "Connection pool is full" warnings when making many
    concurrent requests to the same host (e.g., conda.anaconda.org, ghcr.io).

    Args:
        pool_connections: Number of connection pools to cache
        pool_maxsize: Maximum number of connections in each pool
        max_retries: Number of retries for failed requests

    Returns:
        Configured requests.Session
    """
    session = requests.Session()

    # Configure retries
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )

    # Create adapter with larger connection pool
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=retry_strategy,
    )

    # Mount adapter for both http and https
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


# Global session for module-level usage with thread-safe initialization
_global_session: requests.Session | None = None
_global_session_lock = threading.Lock()


def get_global_session() -> requests.Session:
    """
    Get or create a global session with large connection pool.

    This is useful for modules that make many requests and want to
    share a single session across all functions.

    Thread-safe: uses double-checked locking pattern for initialization.
    """
    global _global_session
    if _global_session is None:
        with _global_session_lock:
            # Double-check after acquiring lock
            if _global_session is None:
                _global_session = create_session_with_large_pool()
    return _global_session


def close_global_session() -> None:
    """
    Close and reset the global session.

    Useful for cleanup in tests or when reconfiguring the session.
    Thread-safe.
    """
    global _global_session
    with _global_session_lock:
        if _global_session is not None:
            _global_session.close()
            _global_session = None
