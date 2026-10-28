"""Authenticate one enrolled user from a webcam."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from biometric_auth.coordinator import AuthenticationCoordinator, PartyClient
from biometric_auth.coordinator.webcam import (
    build_webcam_authentication,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--enrollment-id", default="v1")
    parser.add_argument("--token", required=True)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--cosine-threshold",
        type=float,
        default=0.363,
        help="cosine similarity threshold for SFace match (official default: 0.363)",
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    parties = tuple(
        PartyClient(f"http://127.0.0.1:{8000 + index}", args.token)
        for index in range(1, 4)
    )
    coordinator = AuthenticationCoordinator(parties, cosine_threshold=args.cosine_threshold)
    authentication = build_webcam_authentication(coordinator, args.root, args.camera_index)

    print(f"\n[AUTHENTICATION] Opening camera for user '{args.user_id}' (threshold: {args.cosine_threshold:.4f})...")
    print("Press 'A' in the webcam window when your face is centered, or 'Q' to cancel.")
    t_cam_start = time.perf_counter()
    embedding = authentication.capture_embedding_from_webcam()
    t_cam = (time.perf_counter() - t_cam_start) * 1000

    print(f"\n{'=' * 65}")
    print("           AUTHENTICATION COMPUTATION LOG")
    print(f"{'=' * 65}")
    print("[Identity Context]")
    print(f"  • User ID:             {args.user_id}")
    print(f"  • Enrollment ID:       {args.enrollment_id}")
    print(f"  • Cosine Threshold:    {args.cosine_threshold:.4f}")

    norm_val = float(np.linalg.norm(embedding))
    print("\n[Vision Pipeline - OpenCV YuNet / SFace]")
    print(f"  • Camera & Processing: {t_cam:.2f} ms")
    print(f"  • Feature Vector:      {len(embedding)} dimensions (L2-norm: {norm_val:.4f})")

    print("\n[Secure Multi-Party Computation - 3 Parties / Shamir (t=2, n=3)]")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="ascii") as query_file:
        import json

        json.dump(embedding.tolist(), query_file)
        query_file.flush()
        t_mpc_start = time.perf_counter()
        completed = subprocess.run(
            [
                str(args.root / "venv/bin/python"),
                str(args.root / "scripts/mpyc_persisted_auth.py"),
                "-M",
                "3",
                "--user-id",
                args.user_id,
                "--enrollment-id",
                args.enrollment_id,
                "--query-file",
                query_file.name,
                "--data-dir",
                str(args.data_dir),
                "--cosine-threshold",
                str(args.cosine_threshold),
            ],
            cwd=args.root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        t_mpc = (time.perf_counter() - t_mpc_start) * 1000

    if completed.returncode != 0:
        raise RuntimeError(f"secure authentication failed: {completed.stderr or completed.stdout}")

    for line in completed.stdout.splitlines():
        if line.strip().startswith("•"):
            print(f"  {line.strip()}")

    t_total = t_cam + t_mpc
    print("\n[Latency Summary]")
    print(f"  • Vision Stage:        {t_cam:.2f} ms")
    print(f"  • Secure MPC Stage:    {t_mpc:.2f} ms")
    print(f"  • Total Authentication:{t_total:.2f} ms")

    accepted = "ACCEPT" in completed.stdout
    decision_text = "ACCEPT (MATCH)" if accepted else "REJECT (MISMATCH)"
    print(f"{'=' * 65}")
    print(f"DECISION: {decision_text}")
    print(f"{'=' * 65}\n")
    print("ACCEPT" if accepted else "REJECT")


if __name__ == "__main__":
    main()