"""Calibrate a cosine-similarity threshold from measured score samples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def confusion(scores: list[float], threshold: float, genuine: bool) -> tuple[int, int]:
    if genuine:
        errors = sum(score < threshold for score in scores)
    else:
        errors = sum(score >= threshold for score in scores)
    return errors, len(scores)


def calibrate(genuine: list[float], impostor: list[float]) -> dict[str, Any]:
    if not genuine or not impostor:
        raise ValueError("both genuine and impostor score lists are required")
    if any(not 0.0 <= score <= 1.0 for score in genuine + impostor):
        raise ValueError("cosine scores must be in [0, 1]")

    candidates = sorted(set(genuine + impostor))
    candidates += [0.0, 1.0]
    best: dict[str, Any] | None = None
    for threshold in candidates:
        false_rejects, genuine_count = confusion(genuine, threshold, genuine=True)
        false_accepts, impostor_count = confusion(impostor, threshold, genuine=False)
        result = {
            "threshold": threshold,
            "false_accept_rate": false_accepts / impostor_count,
            "false_reject_rate": false_rejects / genuine_count,
            "balanced_error_rate": (false_accepts / impostor_count + false_rejects / genuine_count) / 2,
            "genuine_count": genuine_count,
            "impostor_count": impostor_count,
        }
        if best is None or (result["balanced_error_rate"], result["threshold"]) < (
            best["balanced_error_rate"],
            best["threshold"],
        ):
            best = result
    assert best is not None
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/threshold.json"))
    args = parser.parse_args()
    payload = json.loads(args.scores.read_text(encoding="utf-8"))
    result = calibrate(list(payload["genuine"]), list(payload["impostor"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()