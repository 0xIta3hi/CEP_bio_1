"""Run the secure fixed-point authentication computation with deterministic vectors."""

from __future__ import annotations

import argparse

import numpy as np
from mpyc.runtime import mpc

from biometric_auth.crypto import FIELD_MODULUS, FixedPointCodec, generate_shares


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match", action="store_true")
    return parser.parse_args()


async def compute(match: bool) -> None:
    codec = FixedPointCodec(fractional_bits=12)
    scale = codec.scale
    template = np.zeros(128, dtype=np.float32)
    template[0] = 1.0
    query = template.copy() if match else np.zeros(128, dtype=np.float32)
    template_encoded = tuple(value + scale for value in codec.encode(template))
    query_encoded = tuple(value + scale for value in codec.encode(query))
    persisted_shares = generate_shares(template_encoded, threshold=2, party_count=3)

    secint = mpc.SecInt(64, p=FIELD_MODULUS)
    lagrange_at_zero = (3, -3, 1)
    template_values = []
    for position in range(128):
        shared_coordinate = []
        for sender in range(3):
            value = persisted_shares[mpc.pid].values[position] if sender == mpc.pid else None
            shared_coordinate.append(mpc.input(secint(value), senders=sender))
        template_values.append(
            sum(coefficient * item for coefficient, item in zip(lagrange_at_zero, shared_coordinate))
            - scale
        )

    query_values = [
        mpc.input(secint(value if mpc.pid == 0 else None), senders=0) - scale
        for value in query_encoded
    ]
    dot_product = sum(template_value * query_value for template_value, query_value in zip(template_values, query_values))
    accepted = dot_product >= codec.threshold_to_scaled_dot_product(0.9)
    result = await mpc.output(accepted, receivers=0)
    if mpc.pid == 0:
        print(f"decision={'ACCEPT' if result else 'REJECT'}")


def main() -> None:
    args = parse_args()
    mpc.run(mpc.start())
    mpc.run(compute(args.match))
    mpc.run(mpc.shutdown())


if __name__ == "__main__":
    main()