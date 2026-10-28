"""Run controlled security experiments against an in-process party service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from biometric_auth.crypto import generate_shares
from biometric_auth.parties.service import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("artifacts/security-party.sqlite3"))
    args = parser.parse_args()
    token = "security-experiment-token"
    client = TestClient(create_app(args.database, token))
    share = generate_shares((1, 2, 3))[0]
    payload = {
        "user_id": "security-test",
        "enrollment_id": "v1",
        "share": share.to_bytes().decode("ascii"),
    }
    headers = {"X-Party-Token": token}

    results = {
        "unauthenticated_get": client.get("/shares/security-test/v1").status_code,
        "initial_create": client.put("/shares", headers=headers, json=payload).status_code,
        "replayed_create": client.put("/shares", headers=headers, json=payload).status_code,
        "tampered_share": client.post(
            "/shares",
            headers=headers,
            json={**payload, "share": payload["share"][:-1] + "0"},
        ).status_code,
        "unexpected_field": client.put(
            "/shares", headers=headers, json={**payload, "unexpected": True}
        ).status_code,
        "cleanup": client.delete("/shares/security-test/v1", headers=headers).status_code,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()