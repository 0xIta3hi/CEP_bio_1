"""Run one authenticated party service using the project virtual environment."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from biometric_auth.parties.service import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--party-id", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--token", default=os.environ.get("PARTY_API_TOKEN", ""))
    args = parser.parse_args()
    if not args.token:
        parser.error("--token or PARTY_API_TOKEN is required")
    port = args.port or 8000 + args.party_id
    database = args.data_dir / f"party-{args.party_id}.sqlite3"
    uvicorn.run(create_app(database, args.token), host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()