"""OpenCV YuNet/SFace face-processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class FaceProcessingError(ValueError):
    """Raised when an input cannot produce exactly one valid embedding."""


@dataclass(frozen=True)
class FacePipeline:
    detector_model: Path
    recognizer_model: Path
    confidence_threshold: float = 0.9
    nms_threshold: float = 0.3
    top_k: int = 5000

    def __post_init__(self) -> None:
        if not self.detector_model.is_file():
            raise FileNotFoundError(self.detector_model)
        if not self.recognizer_model.is_file():
            raise FileNotFoundError(self.recognizer_model)
        detector = cv2.FaceDetectorYN_create(
            str(self.detector_model),
            "",
            (320, 320),
            self.confidence_threshold,
            self.nms_threshold,
            self.top_k,
        )
        recognizer = cv2.FaceRecognizerSF_create(str(self.recognizer_model), "")
        object.__setattr__(self, "_detector", detector)
        object.__setattr__(self, "_recognizer", recognizer)

    def embedding_from_path(self, image_path: Path) -> np.ndarray:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FaceProcessingError(f"cannot decode image: {image_path}")
        return self.embedding_from_image(image)

    def embedding_from_image(self, image: np.ndarray) -> np.ndarray:
        if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
            raise FaceProcessingError("expected a BGR image with shape (height, width, 3)")
        if image.shape[0] < 1 or image.shape[1] < 1:
            raise FaceProcessingError("image dimensions must be positive")
        if image.dtype != np.uint8:
            raise FaceProcessingError("expected an 8-bit BGR image")

        self._detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = self._detector.detect(image)
        if faces is None or len(faces) != 1:
            count = 0 if faces is None else len(faces)
            raise FaceProcessingError(f"expected exactly one face, detected {count}")
        face = np.asarray(faces[0], dtype=np.float32)
        if face.shape != (15,) or not np.isfinite(face).all() or face[-1] < self.confidence_threshold:
            raise FaceProcessingError("detector returned an invalid face record")

        aligned = self._recognizer.alignCrop(image, face)
        feature = self._recognizer.feature(aligned)
        embedding = np.asarray(feature, dtype=np.float32).reshape(-1)
        if embedding.shape != (128,) or not np.isfinite(embedding).all():
            raise FaceProcessingError(f"recognizer returned invalid embedding shape {embedding.shape}")
        norm = float(np.linalg.norm(embedding))
        if not np.isfinite(norm) or norm <= 0:
            raise FaceProcessingError("recognizer returned a zero or invalid embedding")
        return (embedding / norm).astype(np.float32, copy=False)

    @staticmethod
    def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
        left_vector = FacePipeline._validate_embedding(left)
        right_vector = FacePipeline._validate_embedding(right)
        return float(np.dot(left_vector, right_vector))

    @staticmethod
    def _validate_embedding(embedding: np.ndarray) -> np.ndarray:
        vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vector.shape != (128,) or not np.isfinite(vector).all():
            raise FaceProcessingError("expected a finite 128-dimensional embedding")
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 0:
            raise FaceProcessingError("embedding norm must be positive")
        return vector / norm