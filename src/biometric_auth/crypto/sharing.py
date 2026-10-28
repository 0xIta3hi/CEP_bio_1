"""Validated Shamir secret sharing over a fixed prime field."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass

FIELD_MODULUS = (1 << 127) - 1


@dataclass(frozen=True)
class Share:
    index: int
    values: tuple[int, ...]
    threshold: int
    party_count: int
    field_modulus: int = FIELD_MODULUS

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "index": self.index,
                "values": list(self.values),
                "threshold": self.threshold,
                "party_count": self.party_count,
                "field_modulus": self.field_modulus,
            },
            separators=(",", ":"),
        ).encode("ascii")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Share":
        try:
            payload = json.loads(data.decode("ascii"))
            share = cls(
                index=int(payload["index"]),
                values=tuple(int(value) for value in payload["values"]),
                threshold=int(payload["threshold"]),
                party_count=int(payload["party_count"]),
                field_modulus=int(payload["field_modulus"]),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid serialized share") from exc
        _validate_share(share)
        return share


def generate_shares(
    secret: tuple[int, ...] | list[int], threshold: int = 2, party_count: int = 3
) -> tuple[Share, ...]:
    values = tuple(int(value) for value in secret)
    if not values:
        raise ValueError("secret must not be empty")
    if not 1 <= threshold <= party_count:
        raise ValueError("threshold must be between 1 and party_count")
    if any(value <= -(FIELD_MODULUS // 2) or value >= FIELD_MODULUS // 2 for value in values):
        raise ValueError("secret values must fit the signed field representation")

    coefficients = []
    for value in values:
        coefficients.append(
            [value % FIELD_MODULUS]
            + [secrets.randbelow(FIELD_MODULUS) for _ in range(threshold - 1)]
        )

    shares = []
    for index in range(1, party_count + 1):
        shares.append(
            Share(
                index=index,
                values=tuple(_evaluate(polynomial, index) for polynomial in coefficients),
                threshold=threshold,
                party_count=party_count,
            )
        )
    return tuple(shares)


def reconstruct(shares: list[Share] | tuple[Share, ...]) -> tuple[int, ...]:
    if not shares:
        raise ValueError("at least one share is required")
    first = shares[0]
    for share in shares:
        _validate_share(share)
        if (share.threshold, share.party_count, share.field_modulus) != (
            first.threshold,
            first.party_count,
            first.field_modulus,
        ):
            raise ValueError("shares have incompatible parameters")
    if len({share.index for share in shares}) != len(shares):
        raise ValueError("duplicate share index")
    if len(shares) < first.threshold:
        raise ValueError("insufficient shares for reconstruction")

    result = []
    for position in range(len(first.values)):
        value = 0
        for share in shares:
            numerator = 1
            denominator = 1
            for other in shares:
                if other.index == share.index:
                    continue
                numerator = numerator * (-other.index) % first.field_modulus
                denominator = denominator * (share.index - other.index) % first.field_modulus
            coefficient = numerator * pow(denominator, -1, first.field_modulus)
            value = (value + share.values[position] * coefficient) % first.field_modulus
        result.append(value if value < first.field_modulus // 2 else value - first.field_modulus)
    return tuple(result)


def _evaluate(coefficients: list[int], x: int) -> int:
    value = 0
    for coefficient in reversed(coefficients):
        value = (value * x + coefficient) % FIELD_MODULUS
    return value


def _validate_share(share: Share) -> None:
    if share.field_modulus != FIELD_MODULUS:
        raise ValueError("unsupported field modulus")
    if not 1 <= share.index <= share.party_count:
        raise ValueError("share index is outside party range")
    if not 1 <= share.threshold <= share.party_count:
        raise ValueError("invalid share threshold")
    if not share.values:
        raise ValueError("share has no values")
    if any(value < 0 or value >= share.field_modulus for value in share.values):
        raise ValueError("share value is outside field range")