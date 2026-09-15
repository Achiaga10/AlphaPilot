"""Strict GET-only Alpaca Trading API adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import httpx


class AlpacaReadOnlyClient:
    """Read account evidence without exposing any broker mutation method."""

    PAPER_BASE_URL = "https://paper-api.alpaca.markets"
    LIVE_BASE_URL = "https://api.alpaca.markets"

    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        environment: str,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if environment not in {"PAPER", "LIVE"}:
            raise ValueError("Alpaca environment must be PAPER or LIVE")
        if not api_key or not secret_key:
            raise ValueError("Alpaca read-only synchronization credentials are not configured")
        self.environment = environment
        self.base_url = self.PAPER_BASE_URL if environment == "PAPER" else self.LIVE_BASE_URL
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_seconds,
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
            },
        )

    async def close(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def get_account(self) -> dict[str, Any]:
        return await self._get_object("/v2/account")

    async def get_positions(self) -> list[dict[str, Any]]:
        return await self._get_list("/v2/positions")

    async def get_orders(self, *, after: datetime) -> list[dict[str, Any]]:
        return await self._get_list(
            "/v2/orders",
            params={
                "status": "all",
                "after": after.isoformat(),
                "direction": "asc",
                "nested": "true",
                "limit": 500,
            },
        )

    async def get_fill_activities(self, *, after: datetime) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {
                "after": after.isoformat(),
                "direction": "asc",
                "page_size": 100,
            }
            if page_token:
                params["page_token"] = page_token
            response = await self._client.get("/v2/account/activities/FILL", params=params)
            response.raise_for_status()
            page = cast(object, response.json())
            if not isinstance(page, list):
                raise RuntimeError("Alpaca fill activities response must be a list")
            typed_page = [cast(dict[str, Any], item) for item in page if isinstance(item, dict)]
            output.extend(typed_page)
            if len(typed_page) < 100:
                break
            next_token = typed_page[-1].get("id")
            if not isinstance(next_token, str) or not next_token or next_token == page_token:
                raise RuntimeError("Alpaca fill activities pagination did not advance")
            page_token = next_token
        return output

    async def get_clock(self) -> dict[str, Any]:
        return await self._get_object("/v2/clock")

    async def _get_object(self, path: str) -> dict[str, Any]:
        response = await self._client.get(path)
        response.raise_for_status()
        payload = cast(object, response.json())
        if not isinstance(payload, dict):
            raise RuntimeError(f"Alpaca {path} response must be an object")
        return cast(dict[str, Any], payload)

    async def _get_list(
        self, path: str, *, params: dict[str, str | int] | None = None
    ) -> list[dict[str, Any]]:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        payload = cast(object, response.json())
        if not isinstance(payload, list):
            raise RuntimeError(f"Alpaca {path} response must be a list")
        return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]
