from pathlib import Path

import httpx
import numpy as np
import pytest

from biometric_auth.coordinator import AuthenticationCoordinator, AuthenticationError, PartyClient
from biometric_auth.crypto import FixedPointCodec, generate_shares
from biometric_auth.parties.service import create_app


def build_coordinator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthenticationCoordinator:
    apps = [create_app(tmp_path / f"party-{index}.sqlite3", "test-token") for index in range(3)]
    transports = [httpx.ASGITransport(app=app) for app in apps]
    parties = tuple(PartyClient(f"http://party-{index}", "test-token") for index in range(3))
    original_request = PartyClient._request

    async def routed_request(
        self: PartyClient,
        http_client: httpx.AsyncClient,
        method: str,
        path: str,
        **kwargs: object,
    ) -> httpx.Response:
        index = int(self.base_url.rsplit("-", 1)[1])
        http_client._transport = transports[index]
        return await original_request(self, http_client, method, path, **kwargs)

    monkeypatch.setattr(PartyClient, "_request", routed_request)
    return AuthenticationCoordinator(parties)


async def store_template(
    coordinator: AuthenticationCoordinator,
    user_id: str,
    enrollment_id: str,
    values: tuple[int, ...],
) -> None:
    shares = generate_shares(values)
    async with httpx.AsyncClient() as client:
        for party, share in zip(coordinator.parties, shares):
            await party.create_share(client, user_id, enrollment_id, share)


@pytest.mark.anyio
async def test_authentication_accepts_matching_embedding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = build_coordinator(tmp_path, monkeypatch)
    codec = FixedPointCodec()
    embedding = np.zeros(128, dtype=np.float32)
    embedding[0] = 1.0
    await store_template(coordinator, "alice", "v1", codec.encode(embedding))
    assert await coordinator.authenticate("alice", "v1", embedding)


@pytest.mark.anyio
async def test_authentication_rejects_different_embedding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = build_coordinator(tmp_path, monkeypatch)
    codec = FixedPointCodec()
    enrolled = np.zeros(128, dtype=np.float32)
    enrolled[0] = 1.0
    query = np.zeros(128, dtype=np.float32)
    query[1] = 1.0
    await store_template(coordinator, "alice", "v1", codec.encode(enrolled))
    assert not await coordinator.authenticate("alice", "v1", query)


@pytest.mark.anyio
async def test_authentication_fails_closed_when_shares_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator = build_coordinator(tmp_path, monkeypatch)
    with pytest.raises(AuthenticationError, match="shares unavailable"):
        await coordinator.authenticate("missing", "v1", np.zeros(128, dtype=np.float32))