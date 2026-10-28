from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from biometric_auth.crypto import generate_shares
from biometric_auth.parties.service import create_app
from biometric_auth.parties.storage import ShareStore


def test_store_persists_and_rejects_duplicate(tmp_path: Path) -> None:
    database = tmp_path / "party.sqlite3"
    share = generate_shares((1, 2, 3))[0]
    ShareStore(database).put("alice", "enrollment-1", share)
    assert ShareStore(database).get("alice", "enrollment-1") == share
    with pytest.raises(FileExistsError):
        ShareStore(database).put("alice", "enrollment-1", share)


def test_store_replacement_and_deletion(tmp_path: Path) -> None:
    store = ShareStore(tmp_path / "party.sqlite3")
    first, second = generate_shares((1, 2, 3))[:2]
    store.put("alice", "enrollment-1", first)
    store.put("alice", "enrollment-1", second, replace=True)
    assert store.get("alice", "enrollment-1") == second
    assert store.delete("alice", "enrollment-1")
    with pytest.raises(LookupError):
        store.get("alice", "enrollment-1")


def test_service_validates_requests_and_survives_restart(tmp_path: Path) -> None:
    database = tmp_path / "party.sqlite3"
    share = generate_shares((4, 5, 6))[0]
    client = TestClient(create_app(database, "test-token"))
    encoded = share.to_bytes().decode("ascii")
    response = client.put(
        "/shares", headers={"X-Party-Token": "test-token"}, json={"user_id": "alice", "enrollment_id": "e1", "share": encoded}
    )
    assert response.status_code == 204
    assert client.put(
        "/shares", headers={"X-Party-Token": "test-token"}, json={"user_id": "alice", "enrollment_id": "e1", "share": encoded}
    ).status_code == 409
    assert client.get("/shares/alice/e1", headers={"X-Party-Token": "test-token"}).json()["share"] == encoded
    assert client.put("/shares", headers={"X-Party-Token": "test-token"}, json={"user_id": "bad id", "enrollment_id": "e2", "share": encoded}).status_code == 400
    assert client.delete("/shares/alice/e1", headers={"X-Party-Token": "test-token"}).status_code == 204


def test_service_rejects_unauthorized_and_malformed_requests(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "party.sqlite3", "test-token"))
    assert client.get("/shares/alice/e1").status_code == 401
    assert client.put(
        "/shares",
        headers={"X-Party-Token": "test-token"},
        json={"user_id": "alice", "enrollment_id": "e1", "share": "{}"},
    ).status_code == 400
    assert client.put(
        "/shares",
        headers={"X-Party-Token": "test-token", "content-length": "25001"},
        json={"user_id": "alice", "enrollment_id": "e1", "share": "{}"},
    ).status_code == 413


def test_security_experiment_replay_and_tampering_behavior(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "party.sqlite3", "test-token"))
    share = generate_shares((1, 2, 3))[0]
    payload = {
        "user_id": "security-test",
        "enrollment_id": "v1",
        "share": share.to_bytes().decode("ascii"),
    }
    headers = {"X-Party-Token": "test-token"}
    assert client.put("/shares", headers=headers, json=payload).status_code == 204
    assert client.put("/shares", headers=headers, json=payload).status_code == 409
    assert client.post(
        "/shares", headers=headers, json={**payload, "share": payload["share"][:-1] + "0"}
    ).status_code == 400
    assert client.put(
        "/shares", headers=headers, json={**payload, "unexpected": True}
    ).status_code == 422