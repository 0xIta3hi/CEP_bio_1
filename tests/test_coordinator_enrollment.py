from pathlib import Path

import httpx
import pytest

from biometric_auth.coordinator import (
    EnrollmentCoordinator,
    EnrollmentError,
    PartyClient,
    PartyTransportError,
)
from biometric_auth.parties.service import create_app


def coordinator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EnrollmentCoordinator:
    apps = [create_app(tmp_path / f"party-{index}.sqlite3", "test-token") for index in range(3)]
    transports = [httpx.ASGITransport(app=app) for app in apps]
    parties = tuple(PartyClient(f"http://party-{index}", "test-token") for index in range(3))
    client = EnrollmentCoordinator(parties)

    original_request = PartyClient._request

    async def routed_request(self: PartyClient, http_client: httpx.AsyncClient, method: str, path: str, **kwargs: object) -> httpx.Response:
        index = int(self.base_url.rsplit("-", 1)[1])
        http_client._transport = transports[index]
        return await original_request(self, http_client, method, path, **kwargs)

    monkeypatch.setattr(PartyClient, "_request", routed_request)
    return client


@pytest.mark.anyio
async def test_enrollment_replace_delete_and_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enrollment = coordinator(tmp_path, monkeypatch)
    template = tuple(range(128))
    await enrollment.enroll("alice", "v1", template)
    await enrollment.replace("alice", "v1", tuple(range(128, 256)))
    await enrollment.delete("alice", "v1")


@pytest.mark.anyio
async def test_partial_create_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enrollment = coordinator(tmp_path, monkeypatch)
    enrollment = EnrollmentCoordinator(
        (enrollment.parties[0], PartyClient("http://party-failure", "test-token"), enrollment.parties[2])
    )

    original_request = PartyClient._request

    async def request_with_failure(self: PartyClient, *args: object, **kwargs: object) -> httpx.Response:
        if self.base_url == "http://party-failure":
            raise PartyTransportError("simulated party failure")
        return await original_request(self, *args, **kwargs)

    monkeypatch.setattr(PartyClient, "_request", request_with_failure)
    with pytest.raises(EnrollmentError, match="rolled back"):
        await enrollment.enroll("alice", "v1", tuple(range(128)))