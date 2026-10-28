import asyncio
from pathlib import Path

import numpy as np

from biometric_auth.coordinator.webcam import WebcamEnrollment


class FakeCamera:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self.released = False

    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, np.ndarray]:
        return True, self.frame

    def release(self) -> None:
        self.released = True


class FakePipeline:
    def __init__(self) -> None:
        self.calls = 0

    def embedding_from_image(self, frame: np.ndarray) -> np.ndarray:
        self.calls += 1
        return np.eye(1, 128, 0, dtype=np.float32).reshape(-1)


class FakeCoordinator:
    def __init__(self) -> None:
        self.received: tuple[str, str, tuple[int, ...]] | None = None

    async def enroll(self, user_id: str, enrollment_id: str, encoded: tuple[int, ...]) -> None:
        self.received = (user_id, enrollment_id, encoded)


def test_capture_rejects_closed_camera() -> None:
    camera = FakeCamera(np.zeros((20, 20, 3), dtype=np.uint8))
    camera.isOpened = lambda: False  # type: ignore[method-assign]
    enrollment = WebcamEnrollment(FakePipeline(), FakeCoordinator())  # type: ignore[arg-type]
    try:
        enrollment._capture_frame(camera)
    except RuntimeError as exc:
        assert "cannot open camera" in str(exc)


def test_capture_reads_frame_without_persisting_it() -> None:
    camera = FakeCamera(np.zeros((20, 20, 3), dtype=np.uint8))
    enrollment = WebcamEnrollment(FakePipeline(), FakeCoordinator())  # type: ignore[arg-type]
    enrollment.pipeline.embedding_from_image = lambda frame: np.ones(128, dtype=np.float32)  # type: ignore[method-assign]

    import biometric_auth.coordinator.webcam as webcam

    original_wait_key = webcam.cv2.waitKey
    original_imshow = webcam.cv2.imshow
    webcam.cv2.waitKey = lambda _: ord("e")
    webcam.cv2.imshow = lambda *_: None
    try:
        assert enrollment._capture_frame(camera) is camera.frame
    finally:
        webcam.cv2.waitKey = original_wait_key
        webcam.cv2.imshow = original_imshow