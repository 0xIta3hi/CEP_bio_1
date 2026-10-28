from pathlib import Path

import cv2
import numpy as np
import pytest

from biometric_auth.face import FacePipeline, FaceProcessingError


ROOT = Path(__file__).resolve().parents[1]
DETECTOR = ROOT / "models/face_detection_yunet_2023mar.onnx"
RECOGNIZER = ROOT / "models/face_recognition_sface_2021dec.onnx"


@pytest.fixture(scope="module")
def pipeline() -> FacePipeline:
    return FacePipeline(DETECTOR, RECOGNIZER)


def test_invalid_image_is_rejected(pipeline: FacePipeline) -> None:
    with pytest.raises(FaceProcessingError, match="expected a BGR image"):
        pipeline.embedding_from_image(np.zeros((10, 10), dtype=np.uint8))


def test_no_face_is_rejected(pipeline: FacePipeline) -> None:
    image = np.zeros((320, 320, 3), dtype=np.uint8)
    with pytest.raises(FaceProcessingError, match="exactly one face"):
        pipeline.embedding_from_image(image)


def test_embedding_validation_and_cosine_similarity(pipeline: FacePipeline) -> None:
    vector = np.ones(128, dtype=np.float32)
    assert pipeline.cosine_similarity(vector, vector) == pytest.approx(1.0)
    with pytest.raises(FaceProcessingError, match="128-dimensional"):
        pipeline.cosine_similarity(np.ones(127, dtype=np.float32), vector)


def test_corrupt_path_is_rejected(pipeline: FacePipeline, tmp_path: Path) -> None:
    path = tmp_path / "corrupt.jpg"
    path.write_bytes(b"not an image")
    with pytest.raises(FaceProcessingError, match="cannot decode"):
        pipeline.embedding_from_path(path)