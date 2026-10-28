"""Coordinator enrollment lifecycle with rollback on partial failure."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from biometric_auth.coordinator.transport import PartyClient, PartyTransportError
from biometric_auth.crypto import Share, generate_shares


class EnrollmentError(RuntimeError):
    """Raised when enrollment state cannot be made consistent across parties."""


@dataclass(frozen=True)
class EnrollmentCoordinator:
    parties: tuple[PartyClient, ...]
    threshold: int = 2

    def __post_init__(self) -> None:
        if len(self.parties) != 3:
            raise ValueError("exactly three parties are required")
        if self.threshold != 2:
            raise ValueError("the current three-party configuration requires threshold 2")

    async def enroll(
        self, user_id: str, enrollment_id: str, encoded_template: tuple[int, ...]
    ) -> None:
        shares = generate_shares(encoded_template, threshold=self.threshold, party_count=3)
        async with httpx.AsyncClient() as client:
            completed: list[PartyClient] = []
            try:
                for party, share in zip(self.parties, shares):
                    await party.create_share(client, user_id, enrollment_id, share)
                    completed.append(party)
            except PartyTransportError as exc:
                for party in completed:
                    await party.delete_share(client, user_id, enrollment_id)
                raise EnrollmentError("enrollment rolled back after party failure") from exc

    async def replace(
        self, user_id: str, enrollment_id: str, encoded_template: tuple[int, ...]
    ) -> None:
        shares = generate_shares(encoded_template, threshold=self.threshold, party_count=3)
        async with httpx.AsyncClient() as client:
            previous = []
            replaced: list[int] = []
            try:
                previous = [
                    await party.get_share(client, user_id, enrollment_id) for party in self.parties
                ]
                for index, (party, share) in enumerate(zip(self.parties, shares)):
                    await party.replace_share(client, user_id, enrollment_id, share)
                    replaced.append(index)
            except PartyTransportError as exc:
                if len(previous) != len(self.parties):
                    raise EnrollmentError("replacement failed: existing shares unavailable") from exc
                for index in replaced:
                    try:
                        await self.parties[index].replace_share(
                            client, user_id, enrollment_id, previous[index]
                        )
                    except PartyTransportError:
                        raise EnrollmentError("replacement rollback failed; manual repair required") from exc
                raise EnrollmentError("replacement rolled back after party failure") from exc

    async def delete(self, user_id: str, enrollment_id: str) -> None:
        async with httpx.AsyncClient() as client:
            errors = []
            for party in self.parties:
                try:
                    await party.delete_share(client, user_id, enrollment_id)
                except PartyTransportError as exc:
                    errors.append(exc)
            if errors:
                raise EnrollmentError("enrollment deletion incomplete") from errors[0]