import numpy as np
import pytest

from biometric_auth.crypto import FixedPointCodec, Share, generate_shares, reconstruct


def test_fixed_point_round_trip_and_error_bound() -> None:
    codec = FixedPointCodec(fractional_bits=16)
    embedding = np.linspace(-1.0, 1.0, 128, dtype=np.float32)
    decoded = codec.decode(codec.encode(embedding))
    assert np.max(np.abs(embedding - decoded)) <= 2 ** -17
    assert codec.quantization_error(embedding) <= 2 ** -17


def test_fixed_point_rejects_invalid_values() -> None:
    codec = FixedPointCodec()
    with pytest.raises(ValueError, match="outside"):
        codec.encode(np.full(128, 1.1))
    with pytest.raises(ValueError, match="threshold"):
        codec.threshold_to_scaled_dot_product(1.1)


def test_shamir_reconstructs_at_threshold() -> None:
    secret = tuple((-100 if index % 2 else index) for index in range(128))
    shares = generate_shares(secret)
    assert reconstruct(shares[:2]) == secret
    assert reconstruct(shares) == secret


def test_shamir_requires_threshold_and_validates_serialization() -> None:
    shares = generate_shares((1, 2, 3))
    with pytest.raises(ValueError, match="insufficient"):
        reconstruct(shares[:1])
    restored = Share.from_bytes(shares[0].to_bytes())
    assert restored == shares[0]
    with pytest.raises(ValueError, match="invalid serialized"):
        Share.from_bytes(b"{}")


def test_shamir_rejects_duplicate_and_malformed_shares() -> None:
    shares = generate_shares((1, 2, 3))
    with pytest.raises(ValueError, match="duplicate"):
        reconstruct((shares[0], shares[0]))
    malformed = Share(0, shares[0].values, 2, 3)
    with pytest.raises(ValueError, match="index"):
        reconstruct((malformed, shares[1]))