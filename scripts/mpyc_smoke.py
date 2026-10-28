"""Exercise the persisted-share-to-MPyC data flow with deterministic vectors."""

from __future__ import annotations

import argparse

from mpyc.runtime import mpc

from biometric_auth.crypto import generate_shares


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=int, default=3)
    parser.add_argument("--query", type=int, default=3)
    parser.add_argument("--threshold", type=int, default=8)
    return parser.parse_args()


async def compute(template_value: int, query_value: int, threshold: int) -> None:
    secret = (template_value,)
    persisted_shares = generate_shares(secret, threshold=2, party_count=3)
    local_share = persisted_shares[mpc.pid].values[0]

    secint = mpc.SecInt(128)
    shared_shares = []
    for sender in range(3):
        value = local_share if sender == mpc.pid else None
        shared_shares.append(mpc.input(secint(value), senders=sender))
    shared_template = sum(shared_shares)
    query = query_value if mpc.pid == 0 else None
    shared_query = mpc.input(secint(query), senders=0)
    shared_distance = (shared_template - shared_query) * (shared_template - shared_query)
    decision = shared_distance <= threshold
    result = await mpc.output(decision, receivers=0)
    if mpc.pid == 0:
        print(f"decision={'ACCEPT' if result else 'REJECT'}")


def main() -> None:
    args = parse_args()
    mpc.run(mpc.start())
    mpc.run(compute(args.template, args.query, args.threshold))
    mpc.run(mpc.shutdown())


if __name__ == "__main__":
    main()