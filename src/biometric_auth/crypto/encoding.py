"""Fixed-point representation for normalized face embeddings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FixedPointCodec:
    """Encode normalized values as signed integers with a power-of-two scale."""

    fractional_bits: int = 16
    dimension: int = 128

    @property
    def scale(self) -> int:
        return 1 << self.fractional_bits

    def encode(self, embedding: np.ndarray) -> tuple[int, ...]:
        vector = self._validate(embedding)
        encoded = np.rint(vector * self.scale).astype(object)
        return tuple(int(value) for value in encoded)

    def decode(self, values: tuple[int, ...] | list[int]) -> np.ndarray:
        if len(values) != self.dimension:
            raise ValueError(f"expected {self.dimension} values")
        result = np.asarray(values, dtype=np.float64) / self.scale
        if not np.isfinite(result).all() or np.any(result < -1.0) or np.any(result > 1.0):
            raise ValueError("decoded values are outside the normalized embedding range")
        return result.astype(np.float32)

    def quantization_error(self, embedding: np.ndarray) -> float:
        vector = self._validate(embedding)
        decoded = self.decode(self.encode(vector))
        return float(np.max(np.abs(vector - decoded)))

    def threshold_to_scaled_dot_product(self, cosine_threshold: float) -> int:
        if not 0.0 <= cosine_threshold <= 1.0:
            raise ValueError("cosine threshold must be in [0, 1]")
        return int(round(cosine_threshold * self.scale * self.scale))

    def _validate(self, embedding: np.ndarray) -> np.ndarray:
        vector = np.asarray(embedding, dtype=np.float64).reshape(-1)
        if vector.shape != (self.dimension,) or not np.isfinite(vector).all():
            raise ValueError(f"expected a finite {self.dimension}-dimensional embedding")
        if np.any(vector < -1.0) or np.any(vector > 1.0):
            raise ValueError("embedding values are outside the normalized range [-1, 1]")
        return vector