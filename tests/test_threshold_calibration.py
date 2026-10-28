import pytest

from scripts.calibrate_threshold import calibrate


def test_calibration_reports_balanced_error_metrics() -> None:
    result = calibrate([0.91, 0.93, 0.95], [0.10, 0.20, 0.30])
    assert result["threshold"] in {0.3, 0.91}
    assert result["false_accept_rate"] == 0.0
    assert result["false_reject_rate"] == 0.0


def test_calibration_rejects_invalid_scores() -> None:
    with pytest.raises(ValueError, match="both genuine"):
        calibrate([], [0.1])
    with pytest.raises(ValueError, match=r"in \[0, 1\]"):
        calibrate([1.1], [0.1])