"""Interactive webcam capture for enrollment."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from biometric_auth.coordinator.authentication import AuthenticationCoordinator
from biometric_auth.coordinator.enrollment import EnrollmentCoordinator
from biometric_auth.crypto import FixedPointCodec
from biometric_auth.face import FacePipeline, FaceProcessingError


class Camera(Protocol):
    def isOpened(self) -> bool: ...

    def read(self) -> tuple[bool, np.ndarray]: ...

    def release(self) -> None: ...


@dataclass(frozen=True)
class WebcamEnrollment:
    pipeline: FacePipeline
    coordinator: EnrollmentCoordinator
    codec: FixedPointCodec = FixedPointCodec()
    camera_index: int = 0
    window_name: str = "Biometric enrollment"

    async def enroll_from_webcam(
        self, user_id: str, enrollment_id: str, replace: bool = False
    ) -> None:
        camera = cv2.VideoCapture(self.camera_index)
        try:
            frame = self._capture_frame(camera)
            embedding = self.pipeline.embedding_from_image(frame)
            encoded = self.codec.encode(embedding)
            if replace:
                await self.coordinator.replace(user_id, enrollment_id, encoded)
            else:
                await self.coordinator.enroll(user_id, enrollment_id, encoded)
        finally:
            camera.release()
            cv2.destroyAllWindows()

    def _capture_frame(self, camera: Camera) -> np.ndarray:
        if not camera.isOpened():
            raise RuntimeError(f"cannot open camera {self.camera_index}")
        while True:
            received, frame = camera.read()
            if not received or not isinstance(frame, np.ndarray):
                raise RuntimeError("camera read failed")
            preview = frame.copy()
            try:
                self.pipeline.embedding_from_image(frame)
                cv2.putText(
                    preview,
                    "Face ready - press E to enroll, Q to cancel",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 220, 0),
                    2,
                )
            except FaceProcessingError as exc:
                cv2.putText(
                    preview,
                    f"{str(exc)[:70]} - press Q to cancel",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )
            cv2.imshow(self.window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                raise RuntimeError("enrollment cancelled")
            if key == ord("e"):
                try:
                    self.pipeline.embedding_from_image(frame)
                except FaceProcessingError:
                    continue
                return frame


@dataclass(frozen=True)
class WebcamAuthentication:
    pipeline: FacePipeline
    coordinator: AuthenticationCoordinator
    camera_index: int = 0
    window_name: str = "Biometric authentication"

    async def authenticate_from_webcam(self, user_id: str, enrollment_id: str) -> bool:
        embedding = self.capture_embedding_from_webcam()
        return await self.coordinator.authenticate(user_id, enrollment_id, embedding)

    def capture_embedding_from_webcam(self) -> np.ndarray:
        camera = cv2.VideoCapture(self.camera_index)
        try:
            frame = self._capture_frame(camera)
            return self.pipeline.embedding_from_image(frame)
        finally:
            camera.release()
            cv2.destroyAllWindows()

    def _capture_frame(self, camera: Camera) -> np.ndarray:
        if not camera.isOpened():
            raise RuntimeError(f"cannot open camera {self.camera_index}")
        while True:
            received, frame = camera.read()
            if not received or not isinstance(frame, np.ndarray):
                raise RuntimeError("camera read failed")
            preview = frame.copy()
            try:
                self.pipeline.embedding_from_image(frame)
                message = "Face ready - press A to authenticate, Q to cancel"
                color = (0, 220, 0)
            except FaceProcessingError as exc:
                message = f"{str(exc)[:70]} - press Q to cancel"
                color = (0, 0, 255)
            cv2.putText(preview, message, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            cv2.imshow(self.window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                raise RuntimeError("authentication cancelled")
            if key == ord("a"):
                try:
                    self.pipeline.embedding_from_image(frame)
                except FaceProcessingError:
                    continue
                return frame


def build_webcam_enrollment(
    coordinator: EnrollmentCoordinator,
    root: Path,
    camera_index: int = 0,
) -> WebcamEnrollment:
    pipeline = FacePipeline(
        root / "models/face_detection_yunet_2023mar.onnx",
        root / "models/face_recognition_sface_2021dec.onnx",
    )
    return WebcamEnrollment(pipeline, coordinator, camera_index=camera_index)


def run_webcam_enrollment(
    enrollment: WebcamEnrollment, user_id: str, enrollment_id: str, replace: bool = False
) -> None:
    asyncio.run(enrollment.enroll_from_webcam(user_id, enrollment_id, replace=replace))


def build_webcam_authentication(
    coordinator: AuthenticationCoordinator, root: Path, camera_index: int = 0
) -> WebcamAuthentication:
    pipeline = FacePipeline(
        root / "models/face_detection_yunet_2023mar.onnx",
        root / "models/face_recognition_sface_2021dec.onnx",
    )
    return WebcamAuthentication(pipeline, coordinator, camera_index=camera_index)


def run_webcam_authentication(
    authentication: WebcamAuthentication, user_id: str, enrollment_id: str
) -> bool:
    return asyncio.run(authentication.authenticate_from_webcam(user_id, enrollment_id))