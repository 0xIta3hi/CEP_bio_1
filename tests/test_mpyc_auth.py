from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_authentication(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / "venv/bin/python"), str(ROOT / "scripts/mpyc_auth_smoke.py"), "-M", "3", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_secure_fixed_point_authentication_accepts_match() -> None:
    completed = run_authentication("--match")
    assert completed.returncode == 0, completed.stderr
    assert "decision=ACCEPT" in completed.stdout


def test_secure_fixed_point_authentication_rejects_nonmatch() -> None:
    completed = run_authentication()
    assert completed.returncode == 0, completed.stderr
    assert "decision=REJECT" in completed.stdout