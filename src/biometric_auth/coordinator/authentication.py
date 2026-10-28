"""Coordinator authentication orchestration over persisted party shares."""

from __future__ import annotations

from dataclasses import dataclass

import logging
import time

import httpx
import numpy as np

from biometric_auth.coordinator.transport import PartyClient, PartyTransportError
from biometric_auth.crypto import FixedPointCodec, reconstruct

logger = logging.getLogger("biometric_auth.coordinator.authentication")


class AuthenticationError(RuntimeError):
    """Raised when authentication cannot safely complete."""


@dataclass(frozen=True)
class AuthenticationCoordinator:
    parties: tuple[PartyClient, ...]
    codec: FixedPointCodec = FixedPointCodec()
    cosine_threshold: float = 0.363

    def __post_init__(self) -> None:
        if len(self.parties) != 3:
            raise ValueError("exactly three parties are required")
        if not 0.0 <= self.cosine_threshold <= 1.0:
            raise ValueError("cosine threshold must be in [0, 1]")

    async def authenticate(
        self, user_id: str, enrollment_id: str, query_embedding: np.ndarray
    ) -> bool:
        t_start = time.perf_counter()
        query = self.codec._validate(query_embedding)
        query_encoded = self.codec.encode(query)
        async with httpx.AsyncClient() as client:
            t_shares_start = time.perf_counter()
            try:
                shares = [
                    await party.get_share(client, user_id, enrollment_id) for party in self.parties
                ]
            except PartyTransportError as exc:
                raise AuthenticationError("authentication failed: shares unavailable") from exc
            t_shares = (time.perf_counter() - t_shares_start) * 1000
        try:
            if len({share.index for share in shares}) != 3:
                raise ValueError("duplicate share indices")
            t_recon_start = time.perf_counter()
            template_encoded = reconstruct(tuple(shares))
            if len(template_encoded) != self.codec.dimension:
                raise ValueError("unexpected template dimension")
            template = self.codec.decode(template_encoded)
            t_recon = (time.perf_counter() - t_recon_start) * 1000

            t_dot_start = time.perf_counter()
            similarity = float(np.dot(template, query))
            t_dot = (time.perf_counter() - t_dot_start) * 1000
        except (TypeError, ValueError, OverflowError) as exc:
            raise AuthenticationError("authentication failed: inconsistent shares") from exc
        is_accepted = bool(np.isfinite(similarity) and similarity >= self.cosine_threshold)
        t_total = (time.perf_counter() - t_start) * 1000
        logger.info(
            "Authentication for '%s'/'%s': score=%.4f (threshold=%.4f) -> %s [shares: %.2fms, recon: %.2fms, dot: %.2fms, total: %.2fms]",
            user_id,
            enrollment_id,
            similarity,
            self.cosine_threshold,
            "ACCEPT" if is_accepted else "REJECT",
            t_shares,
            t_recon,
            t_dot,
            t_total,
        )
        return is_accepted