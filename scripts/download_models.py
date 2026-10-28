"""Download and verify the official OpenCV Zoo face models."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import onnx

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"

ARTIFACTS = {
    "yunet": {
        "filename": "face_detection_yunet_2023mar.onnx",
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "license_url": "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/LICENSE",
        "license": "MIT",
    },
    "sface": {
        "filename": "face_recognition_sface_2021dec.onnx",
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "license_url": "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_recognition_sface/LICENSE",
        "license": "Apache-2.0",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "distributed-biometric-auth/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)


def tensor_shape(value_info: Any) -> list[int | str]:
    dimensions = value_info.type.tensor_type.shape.dim
    result: list[int | str] = []
    for dimension in dimensions:
        if dimension.HasField("dim_value"):
            result.append(dimension.dim_value)
        elif dimension.HasField("dim_param"):
            result.append(dimension.dim_param)
        else:
            result.append("unknown")
    return result


def value_info(value: Any) -> dict[str, Any]:
    return {"name": value.name, "shape": tensor_shape(value)}


def inspect_model(path: Path) -> dict[str, Any]:
    if path.read_bytes()[:40].startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise RuntimeError(f"Downloaded Git LFS pointer instead of model binary: {path}")
    model = onnx.load(path)
    graph = model.graph
    initializer_names = {item.name for item in graph.initializer}
    net = cv2.dnn.readNetFromONNX(str(path))
    return {
        "onnx_ir_version": model.ir_version,
        "opset_imports": [opset.version for opset in model.opset_import],
        "inputs": [value_info(item) for item in graph.input if item.name not in initializer_names],
        "outputs": [value_info(item) for item in graph.output],
        "opencv_output_names": list(net.getUnconnectedOutLayersNames()),
    }


def verify_face_api() -> dict[str, bool]:
    required = ("FaceDetectorYN_create", "FaceRecognizerSF_create")
    availability = {name: hasattr(cv2, name) for name in required}
    if not all(availability.values()):
        raise RuntimeError(f"OpenCV API missing: {availability}")
    return availability


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="redownload existing model files")
    args = parser.parse_args()

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {
        "python": sys.version,
        "opencv": cv2.__version__,
        "artifacts": {},
        "face_api": verify_face_api(),
    }

    for name, artifact in ARTIFACTS.items():
        model_path = MODEL_DIR / artifact["filename"]
        license_path = MODEL_DIR / f"{name}-LICENSE.txt"
        if args.force or not model_path.exists():
            print(f"Downloading {name} model")
            download(artifact["url"], model_path)
        if args.force or not license_path.exists():
            print(f"Downloading {name} license")
            download(artifact["license_url"], license_path)
        metadata["artifacts"][name] = {
            **artifact,
            "sha256": sha256(model_path),
            "license_sha256": sha256(license_path),
            "metadata": inspect_model(model_path),
        }

    manifest_path = MODEL_DIR / "verification.json"
    manifest_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
