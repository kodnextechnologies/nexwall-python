"""HTTP client for the NexWall Developer API v1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

DEFAULT_BASE_URL = "https://nexwall.kodnextech.com/api/developer/v1"
REGISTER_URL = "https://nexwall.kodnextech.com/developers/register"

Wallpaper = Dict[str, Any]


class NexWallError(Exception):
    """Any non-2xx response from the API."""

    def __init__(self, status: int, message: str, retry_after: Optional[int] = None):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message
        self.retry_after = retry_after


class AuthError(NexWallError):
    """401: missing or invalid API key."""


class NotFoundError(NexWallError):
    """404: not found, or not available on your plan."""


class ValidationError(NexWallError):
    """422: invalid query parameters."""


class RateLimitError(NexWallError):
    """429: daily quota or per-minute limit exceeded. See ``retry_after``."""


_ERRORS = {401: AuthError, 404: NotFoundError, 422: ValidationError, 429: RateLimitError}


class NexWallClient:
    """Minimal NexWall API client.

    Args:
        api_key: Your API key. Defaults to the ``NEXWALL_API_KEY`` env variable.
        base_url: Override to route requests through your own proxy.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = api_key or os.environ.get("NEXWALL_API_KEY", "")
        if not self.api_key:
            raise AuthError(401, f"No API key. Set NEXWALL_API_KEY (free key: {REGISTER_URL})")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        #: Values from the most recent response.
        self.plan: Optional[str] = None
        self.remaining_today: Optional[int] = None
        self.rate_limit: Dict[str, Optional[str]] = {}

    # -- endpoints ---------------------------------------------------------

    def categories(self) -> List[Dict[str, Any]]:
        """``GET /categories`` - categories available on your plan."""
        return self._get("/categories")["data"]

    def wallpapers(
        self,
        page: int = 1,
        per_page: int = 50,
        category_id: Optional[int] = None,
        type: Optional[str] = None,
        search: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """``GET /wallpapers`` - one page of results.

        Returns the full response: ``data``, ``current_page``, ``last_page``,
        ``per_page``, ``total``, ``plan``, ``remaining_requests_today``.

        Args:
            per_page: 1-100 (default 50).
            type: ``"image"`` or ``"live"`` (live requires the Ultra plan).
            search: 2-100 characters, matched against tags.
            sort: ``newest``, ``oldest``, ``popular`` or ``random``.
        """
        return self._get(
            "/wallpapers",
            {
                "page": page,
                "per_page": per_page,
                "category_id": category_id,
                "type": type,
                "search": search,
                "sort": sort,
            },
        )

    def category_wallpapers(self, category_id: int, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """``GET /categories/{categoryId}/wallpapers``."""
        return self._get(f"/categories/{category_id}/wallpapers", {"page": page, "per_page": per_page})

    def wallpaper(self, wallpaper_id: int) -> Wallpaper:
        """``GET /wallpapers/{id}``."""
        body = self._get(f"/wallpapers/{wallpaper_id}")
        data = body.get("data")
        return data if isinstance(data, dict) else body

    def random(
        self,
        category_id: Optional[int] = None,
        search: Optional[str] = None,
        type: str = "image",
    ) -> Wallpaper:
        """One random wallpaper (a single request with ``sort=random``)."""
        items = self.wallpapers(per_page=1, category_id=category_id, search=search, type=type, sort="random")["data"]
        if not items:
            raise NotFoundError(404, "No wallpapers matched your filters")
        return items[0]

    # -- helpers -----------------------------------------------------------

    def download(self, wallpaper: Union[Wallpaper, str], path: Union[str, Path]) -> Path:
        """Download a wallpaper's full-size ``image_url`` (or any URL) to ``path``.

        If ``path`` is a directory, the file is named ``nexwall-<id>.<ext>``.
        """
        url = wallpaper if isinstance(wallpaper, str) else wallpaper["image_url"]
        target = Path(path).expanduser()
        if target.is_dir() or str(path).endswith(("/", "\\")):
            ext = Path(url.split("?")[0]).suffix or ".jpg"
            name = f"nexwall-{wallpaper['id']}{ext}" if isinstance(wallpaper, dict) else f"nexwall{ext}"
            target = target / name
        target.parent.mkdir(parents=True, exist_ok=True)

        # The API key is only sent to the API, never to the image host.
        with requests.get(url, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            tmp = target.with_name(target.name + ".part")
            with open(tmp, "wb") as fh:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    fh.write(chunk)
            tmp.replace(target)
        return target

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        clean = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        response = self.session.get(
            self.base_url + path,
            params=clean,
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            timeout=self.timeout,
        )

        self.rate_limit = {
            "limit": response.headers.get("X-RateLimit-Limit"),
            "remaining": response.headers.get("X-RateLimit-Remaining"),
            "reset": response.headers.get("X-RateLimit-Reset"),
            "plan": response.headers.get("X-Developer-Api-Plan"),
        }

        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.ok:
            message = body.get("message") if isinstance(body, dict) else None
            retry_after = response.headers.get("Retry-After")
            if response.status_code == 429:
                self.remaining_today = 0
            error_cls = _ERRORS.get(response.status_code, NexWallError)
            raise error_cls(
                response.status_code,
                message or response.reason or "Request failed",
                int(retry_after) if retry_after and retry_after.isdigit() else None,
            )

        if isinstance(body, dict):
            self.plan = body.get("plan", self.plan)
            remaining = body.get("remaining_requests_today")
            if isinstance(remaining, int):
                self.remaining_today = remaining
        return body
