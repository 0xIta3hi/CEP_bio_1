import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from biometric_auth.crypto import FixedPointCodec, generate_shares
from biometric_auth.parties.storage import ShareStore


ROOT = Path(__file__).resolve().parents[1]


def run_persisted_auth(tmp_path: Path, query: np.ndarray) -> subprocess.CompletedProcess[str]:
    codec = FixedPointCodec()
    template = np.zeros(128, dtype=np.float32)
    template[0] = 1.0
    shares = generate_shares(codec.encode(template))
    for index, share in enumerate(shares, start=1):
        ShareStore(tmp_path / f"party-{index}.sqlite3").put("alice", "v1", share)
    query_path = tmp_path / "query.json"
    query_path.write_text(json.dumps(query.tolist()), encoding="ascii")
    return subprocess.run(
        [
            str(ROOT / "venv/bin/python"),
            str(ROOT / "scripts/mpyc_persisted_auth.py"),
            "-M",
            "3",
            "--user-id",
            "alice",
            "--query-file",
            str(query_path),
            "--data-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_mpyc_reads_independent_persisted_party_shares(tmp_path: Path) -> None:
    query = np.zeros(128, dtype=np.float32)
    query[0] = 1.0
    completed = run_persisted_auth(tmp_path, query)
    assert completed.returncode == 0, completed.stderr
    assert "ACCEPT" in completed.stdout


def test_mpyc_rejects_nonmatching_persisted_query(tmp_path: Path) -> None:
    query = np.zeros(128, dtype=np.float32)
    query[1] = 1.0
    completed = run_persisted_auth(tmp_path, query)
    assert completed.returncode == 0, completed.stderr
    assert "REJECT" in completed.stdout