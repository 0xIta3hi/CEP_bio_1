"""HTTP service exposing one party's independent share store."""

from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from biometric_auth.crypto import Share
from biometric_auth.parties.storage import ShareStore


class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=64)
    enrollment_id: str = Field(min_length=1, max_length=64)
    share: str = Field(min_length=1, max_length=20000)


def create_app(database_path: Path, api_token: str) -> FastAPI:
    if not api_token:
        raise ValueError("api_token is required")
    app = FastAPI(title="Biometric Authentication Party", docs_url=None, redoc_url=None)
    store = ShareStore(database_path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.put("/shares", status_code=204)
    async def put_share(payload: ShareRequest, request: Request) -> None:
        _authenticate(request, api_token)
        _check_content_length(request)
        try:
            share = Share.from_bytes(payload.share.encode("ascii"))
            store.put(payload.user_id, payload.enrollment_id, share)
        except (UnicodeEncodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid share payload") from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail="enrollment already exists") from exc

    @app.post("/shares", status_code=204)
    async def replace_share(payload: ShareRequest, request: Request) -> None:
        _authenticate(request, api_token)
        _check_content_length(request)
        try:
            share = Share.from_bytes(payload.share.encode("ascii"))
            store.put(payload.user_id, payload.enrollment_id, share, replace=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid share payload") from exc

    @app.get("/shares/{user_id}/{enrollment_id}")
    def get_share(user_id: str, enrollment_id: str, request: Request) -> dict[str, str]:
        _authenticate(request, api_token)
        try:
            share = store.get(user_id, enrollment_id)
        except (ValueError, LookupError) as exc:
            raise HTTPException(status_code=404, detail="share unavailable") from exc
        return {"share": share.to_bytes().decode("ascii")}

    @app.delete("/shares/{user_id}/{enrollment_id}", status_code=204)
    def delete_share(user_id: str, enrollment_id: str, request: Request) -> None:
        _authenticate(request, api_token)
        try:
            deleted = store.delete(user_id, enrollment_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid identifier") from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="share unavailable")

    return app


def _check_content_length(request: Request) -> None:
    raw_length = request.headers.get("content-length")
    try:
        content_length = int(raw_length) if raw_length is not None else 0
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid content length") from exc
    if content_length > 25000:
        raise HTTPException(status_code=413, detail="request too large")


def _authenticate(request: Request, api_token: str) -> None:
    supplied = request.headers.get("X-Party-Token", "")
    if not hmac.compare_digest(supplied, api_token):
        raise HTTPException(status_code=401, detail="unauthorized")