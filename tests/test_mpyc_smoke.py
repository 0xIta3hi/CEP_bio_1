from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_three_party_mpyc_persisted_share_flow() -> None:
    command = [
        str(ROOT / "venv/bin/python"),
        str(ROOT / "scripts/mpyc_smoke.py"),
        "-M",
        "3",
        "--template",
        "3",
        "--query",
        "3",
        "--threshold",
        "0",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert "decision=ACCEPT" in completed.stdout