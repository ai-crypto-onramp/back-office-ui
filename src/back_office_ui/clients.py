from __future__ import annotations

from typing import Any

import httpx


class BackendClient:
    """Thin httpx wrapper for calling backend services."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base, timeout=timeout)

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._client.get(path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._client.post(path, **kwargs)

    def close(self) -> None:
        self._client.close()
