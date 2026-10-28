"""Measure deterministic crypto and persisted MPyC authentication overhead."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
import math
from pathlib import Path

import numpy as np

from biometric_auth.crypto import FixedPointCodec, generate_shares
from biometric_auth.parties.storage import ShareStore


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * fraction))
    return ordered[min(len(ordered) - 1, rank - 1)]


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": statistics.median(values) * 1000,
        "p95_ms": percentile(values, 0.95) * 1000,
        "min_ms": min(values) * 1000,
        "max_ms": max(values) * 1000,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("artifacts/benchmark.json"))
    args = parser.parse_args()
    if args.trials < 1 or args.trials > 100:
        parser.error("--trials must be between 1 and 100")

    codec = FixedPointCodec()
    vector = np.zeros(128, dtype=np.float32)
    vector[0] = 1.0
    encoded = codec.encode(vector)
    results: dict[str, object] = {
        "python": subprocess.check_output([sys.executable, "--version"], text=True).strip(),
        "trials": args.trials,
        "dimension": codec.dimension,
        "fractional_bits": codec.fractional_bits,
    }

    encode_times = []
    share_times = []
    for _ in range(args.trials):
        start = time.perf_counter()
        codec.encode(vector)
        encode_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        generate_shares(encoded)
        share_times.append(time.perf_counter() - start)
    results["fixed_point_encode"] = summarize(encode_times)
    results["shamir_generate"] = summarize(share_times)

    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory)
        for index, share in enumerate(generate_shares(encoded), start=1):
            ShareStore(data_dir / f"party-{index}.sqlite3").put("benchmark", "v1", share)
        query = data_dir / "query.json"
        query.write_text(json.dumps(vector.tolist()), encoding="ascii")
        mpc_times = []
        for _ in range(args.trials):
            start = time.perf_counter()
            completed = subprocess.run(
                [
                    str(Path(__file__).resolve().parents[1] / "venv/bin/python"),
                    str(Path(__file__).resolve().parent / "mpyc_persisted_auth.py"),
                    "-M",
                    "3",
                    "--user-id",
                    "benchmark",
                    "--query-file",
                    str(query),
                    "--data-dir",
                    str(data_dir),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            mpc_times.append(time.perf_counter() - start)
            if completed.returncode != 0 or "ACCEPT" not in completed.stdout:
                raise RuntimeError(completed.stderr or completed.stdout)
        results["persisted_mpyc_authentication"] = summarize(mpc_times)
        results["share_bytes_per_party"] = len(generate_shares(encoded)[0].to_bytes())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()