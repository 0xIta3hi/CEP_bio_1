# Distributed Biometric Authentication

This project implements a locally deployable biometric authentication system using OpenCV YuNet/SFace, independent party storage, Shamir secret sharing, and MPyC secure computation.

The implementation is being developed incrementally. It does not claim liveness detection, malicious-party security, production readiness, or independent physical trust domains when all parties run on one host.

## Environment

All project Python commands must use the project virtual environment. Do not use the system interpreter for project execution.

```bash
cd /home/ita3hi/Projects/CEP_bio_1
/usr/bin/python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -e '.[test]'
```

Download and verify the official face models:

```bash
venv/bin/python scripts/download_models.py
```

Verify the selected interpreter:

```bash
venv/bin/python -c "import sys; print(sys.executable); print(sys.version)"
```

## Current status

Phase 1 decisions and the implementation plan are documented in `docs/architecture.md`. Model artifacts are kept out of Git and will be downloaded and verified by a project script from the official OpenCV Zoo sources.

## Planned commands

The following commands will be added as each phase is implemented:

```bash
venv/bin/python -m pytest
venv/bin/python scripts/download_models.py
venv/bin/python scripts/run_parties.py
venv/bin/python scripts/enroll.py
venv/bin/python scripts/authenticate.py
venv/bin/python scripts/benchmark.py
```

## Run party services manually

Open three terminals. Use the same locally generated test token for this development deployment:

```bash
export PARTY_API_TOKEN='local-development-token'
venv/bin/python scripts/run_party.py --party-id 1 --token "$PARTY_API_TOKEN"
venv/bin/python scripts/run_party.py --party-id 2 --token "$PARTY_API_TOKEN"
venv/bin/python scripts/run_party.py --party-id 3 --token "$PARTY_API_TOKEN"
```

The services listen on `127.0.0.1:8001`, `127.0.0.1:8002`, and `127.0.0.1:8003`. Each service writes only its own SQLite database under `data/`. Share endpoints require the `X-Party-Token` header; `/health` is unauthenticated for process liveness checks.

The coordinator lifecycle currently supports create, replacement, deletion, bounded HTTP timeouts, and rollback after a partial create or replacement failure.

## Enroll from a webcam

After the three party services are running, verify the models and start enrollment with:

```bash
venv/bin/python scripts/enroll_webcam.py \
	--user-id alice \
	--enrollment-id v1 \
	--token "$PARTY_API_TOKEN"
```

An existing `(user-id, enrollment-id)` is rejected by default. To intentionally replace it with a fresh webcam capture, add `--replace`:

```bash
venv/bin/python scripts/enroll_webcam.py \
	--user-id alice \
	--enrollment-id v1 \
	--replace \
	--token "$PARTY_API_TOKEN"
```

The default camera is device `0`. Select another device with `--camera-index 1`.

On Linux Wayland sessions, the launcher automatically selects OpenCV's installed `xcb` Qt backend because the `opencv-python` wheel does not include its Wayland plugin. Override it by setting `QT_QPA_PLATFORM` before the command if your environment provides another compatible backend.

The camera window shows a live preview. Keep exactly one face visible, then press `E` to enroll. Press `Q` to cancel. Frames are processed in memory, and raw images are not persisted. Enrollment fails closed if the camera cannot open, a frame cannot be read, the face count is not exactly one, the embedding is invalid, or any party cannot persist its share.

This command implements webcam enrollment only. Webcam authentication and the coordinator's secure authentication endpoint are the next slice.

## Authenticate from a webcam

After enrolling a user, run:

```bash
venv/bin/python scripts/authenticate_webcam.py \
	--user-id alice \
	--enrollment-id v1 \
	--token "$PARTY_API_TOKEN"
```

Press `A` when exactly one face is visible or `Q` to cancel. The command prints only `ACCEPT` or `REJECT`. The enrolled template is read independently by the three MPyC party processes and is not reconstructed by the coordinator. For this local implementation, the temporary query JSON is placed on the shared local filesystem so the party processes can read it; query confidentiality across separate hosts is not yet implemented.

## Benchmark

Run reproducible synthetic measurements with:

```bash
venv/bin/python scripts/benchmark.py --trials 20
```

The benchmark writes `artifacts/benchmark.json`. A two-trial validation run on Python 3.14.8 measured approximately 0.057 ms median fixed-point encoding, 0.358 ms median Shamir generation, 459 ms median persisted MPyC authentication including process startup, and 5,150 serialized bytes per party. These are local synthetic measurements, not face-recognition accuracy or production latency claims.

Run the live end-to-end smoke test against the three running party services:

```bash
venv/bin/python scripts/e2e_smoke.py --token "$PARTY_API_TOKEN"
```

Expected output:

```text
matching_query=ACCEPT
nonmatching_query=REJECT
```

The script uses a synthetic identity and removes it from all three party databases after the run.

## Implementation status

Implemented and tested: official model verification, YuNet/SFace processing, fixed-point encoding, signed Shamir sharing, independent SQLite party persistence, authenticated party APIs, enrollment lifecycle rollback, webcam enrollment, webcam authentication, persisted-share MPyC decision computation, security input validation, and reproducible benchmarking.

Remaining report work: collect genuine/impostor threshold data, run packet/replay/tampering experiments on the actual deployment, measure camera/vision latency separately, and document any confirmed findings without inventing vulnerabilities.

## Threshold calibration

Prepare measured cosine scores in a JSON file:

```json
{"genuine": [0.91, 0.93, 0.95], "impostor": [0.10, 0.20, 0.30]}
```

Then run:

```bash
venv/bin/python scripts/calibrate_threshold.py \
	--scores scores.json \
	--output artifacts/threshold.json
```

The output reports the selected threshold, false-accept rate, false-reject rate, and balanced error rate. Do not use the small example values as an accuracy claim; they are only a format demonstration.
