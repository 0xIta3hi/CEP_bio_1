"""Exercise the live three-party HTTP, persistence, and MPyC pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

import httpx
import numpy as np

from biometric_auth.crypto import FixedPointCodec, generate_shares


async def distribute(base_urls: tuple[str, ...], token: str, user_id: str, enrollment_id: str) -> None:
    codec = FixedPointCodec()
    template = np.zeros(codec.dimension, dtype=np.float32)
    template[0] = 1.0
    shares = generate_shares(codec.encode(template))
    headers = {"X-Party-Token": token}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for base_url, share in zip(base_urls, shares):
            response = await client.put(
                f"{base_url}/shares",
                headers=headers,
                json={
                    "user_id": user_id,
                    "enrollment_id": enrollment_id,
                    "share": share.to_bytes().decode("ascii"),
                },
            )
            response.raise_for_status()


async def cleanup(base_urls: tuple[str, ...], token: str, user_id: str, enrollment_id: str) -> None:
    headers = {"X-Party-Token": token}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for base_url in base_urls:
            await client.delete(f"{base_url}/shares/{user_id}/{enrollment_id}", headers=headers)


def run_decision(
    root: Path, data_dir: Path, query: np.ndarray, user_id: str, enrollment_id: str
) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="ascii") as query_file:
        json.dump(query.tolist(), query_file)
        query_file.flush()
        completed = subprocess.run(
            [
                str(root / "venv/bin/python"),
                str(root / "scripts/mpyc_persisted_auth.py"),
                "-M",
                "3",
                "--user-id",
                user_id,
                "--enrollment-id",
                enrollment_id,
                "--query-file",
                query_file.name,
                "--data-dir",
                str(data_dir),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    for line in completed.stdout.splitlines():
        if line.strip() in {"ACCEPT", "REJECT"}:
            return line.strip()
    raise RuntimeError(f"MPyC decision missing from output: {completed.stdout}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    base_urls = tuple(f"http://127.0.0.1:{8000 + index}" for index in range(1, 4))
    user_id, enrollment_id = "synthetic-e2e", "run"
    template = np.zeros(128, dtype=np.float32)
    template[0] = 1.0
    nonmatch = np.zeros(128, dtype=np.float32)
    nonmatch[1] = 1.0
    asyncio.run(distribute(base_urls, args.token, user_id, enrollment_id))
    try:
        accepted = run_decision(args.root, args.data_dir, template, user_id, enrollment_id)
        rejected = run_decision(args.root, args.data_dir, nonmatch, user_id, enrollment_id)
        print(f"matching_query={accepted}")
        print(f"nonmatching_query={rejected}")
    finally:
        asyncio.run(cleanup(base_urls, args.token, user_id, enrollment_id))


if __name__ == "__main__":
    main()