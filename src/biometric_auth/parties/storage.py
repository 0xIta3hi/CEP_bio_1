"""Independent persistent storage for one party's shares."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from biometric_auth.crypto import Share

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ShareStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shares (
                    user_id TEXT NOT NULL,
                    enrollment_id TEXT NOT NULL,
                    share BLOB NOT NULL,
                    PRIMARY KEY (user_id, enrollment_id)
                )
                """
            )

    def put(self, user_id: str, enrollment_id: str, share: Share, replace: bool = False) -> None:
        _validate_identifier(user_id)
        _validate_identifier(enrollment_id)
        payload = share.to_bytes()
        with self._connect() as connection:
            if replace:
                connection.execute(
                    "INSERT OR REPLACE INTO shares(user_id, enrollment_id, share) VALUES (?, ?, ?)",
                    (user_id, enrollment_id, payload),
                )
            else:
                try:
                    connection.execute(
                        "INSERT INTO shares(user_id, enrollment_id, share) VALUES (?, ?, ?)",
                        (user_id, enrollment_id, payload),
                    )
                except sqlite3.IntegrityError as exc:
                    raise FileExistsError("enrollment already exists") from exc

    def get(self, user_id: str, enrollment_id: str) -> Share:
        _validate_identifier(user_id)
        _validate_identifier(enrollment_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT share FROM shares WHERE user_id = ? AND enrollment_id = ?",
                (user_id, enrollment_id),
            ).fetchone()
        if row is None:
            raise LookupError("share not found")
        try:
            return Share.from_bytes(bytes(row[0]))
        except ValueError as exc:
            raise ValueError("stored share is corrupt") from exc

    def delete(self, user_id: str, enrollment_id: str) -> bool:
        _validate_identifier(user_id)
        _validate_identifier(enrollment_id)
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM shares WHERE user_id = ? AND enrollment_id = ?",
                (user_id, enrollment_id),
            )
        return cursor.rowcount == 1

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _validate_identifier(value: str) -> None:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError("identifier must contain 1-64 ASCII letters, digits, '_' or '-'")