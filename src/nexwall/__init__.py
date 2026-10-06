"""Tiny Python client for the NexWall free wallpaper API.

    >>> from nexwall import NexWallClient
    >>> client = NexWallClient()            # reads NEXWALL_API_KEY
    >>> wallpaper = client.random(category_id=5)
    >>> client.download(wallpaper, "wall.jpg")

Docs: https://nexwall.kodnextech.com/wallpaper-api/docs
"""

from .client import (
    DEFAULT_BASE_URL,
    AuthError,
    NexWallClient,
    NexWallError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "AuthError",
    "NexWallClient",
    "NexWallError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
]
__version__ = "0.1.0"
