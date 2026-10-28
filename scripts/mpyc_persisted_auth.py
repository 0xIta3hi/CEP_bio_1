"""Run authentication through MPyC using each party's own persisted share."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from mpyc.runtime import mpc

from biometric_auth.crypto import FIELD_MODULUS, FixedPointCodec
from biometric_auth.parties.storage import ShareStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--enrollment-id", default="v1")
    parser.add_argument("--query-file", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--cosine-threshold", type=float, default=0.363)
    return parser.parse_args()


import time


async def compute(args: argparse.Namespace) -> None:
    t_start = time.perf_counter()
    codec = FixedPointCodec()
    if mpc.pid == 0:
        query = np.asarray(json.loads(args.query_file.read_text(encoding="ascii")), dtype=np.float32)
        t_enc_start = time.perf_counter()
        query_encoded = codec.encode(query)
        t_encode = (time.perf_counter() - t_enc_start) * 1000
    else:
        query_encoded = tuple(0 for _ in range(codec.dimension))
        t_encode = 0.0

    t_store_start = time.perf_counter()
    store = ShareStore(args.data_dir / f"party-{mpc.pid + 1}.sqlite3")
    share = store.get(args.user_id, args.enrollment_id)
    t_store = (time.perf_counter() - t_store_start) * 1000

    if share.party_count != 3 or share.threshold != 2 or len(share.values) != codec.dimension:
        raise ValueError("persisted share parameters do not match the MPC configuration")

    secint = mpc.SecInt(64, p=FIELD_MODULUS)
    lagrange_at_zero = (3, -3, 1)

    t_input_start = time.perf_counter()
    template_values = []
    for value in share.values:
        inputs = [
            mpc.input(secint(value if mpc.pid == sender else None), senders=sender)
            for sender in range(3)
        ]
        template_values.append(
            sum(coefficient * item for coefficient, item in zip(lagrange_at_zero, inputs))
        )

    query_values = [
        mpc.input(secint(value if mpc.pid == 0 else None), senders=0) for value in query_encoded
    ]
    t_input = (time.perf_counter() - t_input_start) * 1000

    t_dot_start = time.perf_counter()
    dot_product = sum(a * b for a, b in zip(template_values, query_values))
    t_dot = (time.perf_counter() - t_dot_start) * 1000

    t_comp_start = time.perf_counter()
    scaled_threshold = codec.threshold_to_scaled_dot_product(args.cosine_threshold)
    accepted = dot_product >= scaled_threshold
    t_comp = (time.perf_counter() - t_comp_start) * 1000

    result = await mpc.output(accepted, receivers=0)
    score_raw = await mpc.output(dot_product, receivers=0)
    t_total_mpc = (time.perf_counter() - t_start) * 1000

    if mpc.pid == 0:
        score_float = float(score_raw) / (codec.scale ** 2)
        margin = score_float - args.cosine_threshold
        print(f"  • SQLite Share Load (Party 1):  {t_store:.2f} ms")
        print(f"  • Fixed-Point Query Encode:     {t_encode:.2f} ms (scale=2^16)")
        print(f"  • Secret-Sharing 256 inputs:    {t_input:.2f} ms (t=2, n=3)")
        print(f"  • Secret-Shared Dot Product:    {t_dot:.2f} ms (128 coordinates)")
        print(f"  • Secure Threshold Comparison:  {t_comp:.2f} ms (scaled threshold: {scaled_threshold})")
        print(f"  • Reconstructed Cosine Score:   {score_float:.4f} (Threshold: {args.cosine_threshold:.4f}, Margin: {margin:+.4f})")
        print(f"  • MPC Protocol Latency:         {t_total_mpc:.2f} ms")
        print("ACCEPT" if result else "REJECT", flush=True)


def main() -> None:
    args = parse_args()
    mpc.run(mpc.start())
    mpc.run(compute(args))
    mpc.run(mpc.shutdown())


if __name__ == "__main__":
    main()