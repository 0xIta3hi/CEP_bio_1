"""Enroll one face from a webcam into the three party services."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# This OpenCV wheel provides xcb but not the Wayland Qt platform plugin.
if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from biometric_auth.coordinator import EnrollmentCoordinator, EnrollmentError, PartyClient
from biometric_auth.coordinator.webcam import build_webcam_enrollment, run_webcam_enrollment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--enrollment-id", default="v1")
    parser.add_argument("--token", required=True, help="shared party API token")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace the existing enrollment instead of rejecting a duplicate",
    )
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    parties = tuple(
        PartyClient(f"http://127.0.0.1:{8000 + index}", args.token)
        for index in range(1, 4)
    )
    coordinator = EnrollmentCoordinator(parties)
    enrollment = build_webcam_enrollment(coordinator, args.root, args.camera_index)
    try:
        run_webcam_enrollment(
            enrollment, args.user_id, args.enrollment_id, replace=args.replace
        )
    except EnrollmentError as exc:
        parser.error(str(exc))
    print(f"Enrollment successful for user {args.user_id}")


if __name__ == "__main__":
    main()