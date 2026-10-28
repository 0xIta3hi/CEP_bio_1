"""Validated coordinator transport for party share services."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from biometric_auth.crypto import Share


class PartyTransportError(RuntimeError):
    """Raised when a party cannot complete a requested operation."""


@dataclass(frozen=True)
class PartyClient:
    base_url: str
    api_token: str
    timeout_seconds: float = 3.0

    async def health(self, client: httpx.AsyncClient) -> None:
        response = await self._request(client, "GET", "/health")
        if response.status_code != 200 or response.json().get("status") != "ok":
            raise PartyTransportError(f"party health check failed: {self.base_url}")

    async def create_share(
        self, client: httpx.AsyncClient, user_id: str, enrollment_id: str, share: Share
    ) -> None:
        response = await self._request(
            client,
            "PUT",
            "/shares",
            json={
                "user_id": user_id,
                "enrollment_id": enrollment_id,
                "share": share.to_bytes().decode("ascii"),
            },
        )
        if response.status_code != 204:
            raise PartyTransportError(f"share creation failed: HTTP {response.status_code}")

    async def replace_share(
        self, client: httpx.AsyncClient, user_id: str, enrollment_id: str, share: Share
    ) -> None:
        response = await self._request(
            client,
            "POST",
            "/shares",
            json={
                "user_id": user_id,
                "enrollment_id": enrollment_id,
                "share": share.to_bytes().decode("ascii"),
            },
        )
        if response.status_code != 204:
            raise PartyTransportError(f"share replacement failed: HTTP {response.status_code}")

    async def get_share(
        self, client: httpx.AsyncClient, user_id: str, enrollment_id: str
    ) -> Share:
        response = await self._request(client, "GET", f"/shares/{user_id}/{enrollment_id}")
        if response.status_code != 200:
            raise PartyTransportError(f"share retrieval failed: HTTP {response.status_code}")
        try:
            encoded = response.json()["share"].encode("ascii")
            return Share.from_bytes(encoded)
        except (KeyError, TypeError, UnicodeEncodeError, ValueError) as exc:
            raise PartyTransportError("party returned an invalid share") from exc

    async def delete_share(
        self, client: httpx.AsyncClient, user_id: str, enrollment_id: str
    ) -> None:
        response = await self._request(client, "DELETE", f"/shares/{user_id}/{enrollment_id}")
        if response.status_code not in (204, 404):
            raise PartyTransportError(f"share deletion failed: HTTP {response.status_code}")

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        authenticated: bool = True,
        **kwargs: object,
    ) -> httpx.Response:
        try:
            headers = dict(kwargs.pop("headers", {}))
            if authenticated:
                headers["X-Party-Token"] = self.api_token
            return await client.request(
                method,
                f"{self.base_url.rstrip('/')}{path}",
                timeout=self.timeout_seconds,
                headers=headers,
                **kwargs,
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise PartyTransportError(f"party request failed: {self.base_url}") from exc