"""FastAPI routes for protected commissioning configuration and jobs."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from .commissioning_errors import (
    CommissioningBusy,
    CommissioningError,
    CommissioningNotFound,
    CommissioningRevisionConflict,
    CommissioningStateError,
    CommissioningStorageError,
    CommissioningUnavailable,
    CommissioningValidationError,
)
from .commissioning_jobs import CommissioningManager
from .pin_auth import is_pin_configured


class ConfigWriteBody(BaseModel):
    """Raw editor content plus the revision originally loaded by the browser."""

    content: str = Field(description="complete replacement file content")
    revision: str = Field(description="SHA-256 revision returned by the last GET")


class JobCreateBody(BaseModel):
    """One individual or ordered multi-motor hardware operation."""

    subsystem: str = Field(default="core")
    operation: str = Field(description="save or calibrate")
    motor_ids: list[str] = Field(description="one or more catalogued motor IDs")


class CalibrationRequest(BaseModel):
    """Explicit safety acknowledgement used by the legacy wheel route."""

    off_ground_confirmed: bool = Field(
        description="true only after confirming this exact wheel can spin freely"
    )


def require_commissioning_access(request: Request) -> None:
    """Require the existing PIN session whenever a PIN has been configured."""
    if is_pin_configured() and request.session.get("pin_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN authentication is required for commissioning",
        )


def raise_commissioning_http(exc: CommissioningError) -> None:
    """Translate expected domain failures into stable HTTP status codes."""
    if isinstance(exc, CommissioningNotFound):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, CommissioningValidationError):
        status_code = 422
    elif isinstance(
        exc,
        (
            CommissioningBusy,
            CommissioningRevisionConflict,
            CommissioningStateError,
            CommissioningUnavailable,
        ),
    ):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, CommissioningStorageError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def create_commissioning_router(manager: CommissioningManager) -> APIRouter:
    """Create routes around an injected manager for production and tests."""
    router = APIRouter(
        prefix="/api/commissioning",
        tags=["commissioning"],
        dependencies=[Depends(require_commissioning_access)],
    )

    @router.get("/catalog")
    def get_catalog() -> dict:
        return manager.public_catalog()

    @router.get("/configs/{subsystem}/{scope}")
    def get_motor_config(subsystem: str, scope: str) -> dict:
        """Read shared config with scope=shared or an individual motor ID."""
        try:
            return manager.read_motor_config(subsystem, scope)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.put("/configs/{subsystem}/{scope}")
    def put_motor_config(
        subsystem: str,
        scope: str,
        body: ConfigWriteBody,
    ) -> dict:
        try:
            return manager.write_motor_config(
                subsystem,
                scope,
                body.content,
                body.revision,
            )
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.get("/soft-limits/{subsystem}")
    def get_soft_limits(subsystem: str) -> dict:
        try:
            return manager.read_soft_limits(subsystem)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.put("/soft-limits/{subsystem}")
    def put_soft_limits(
        subsystem: str,
        body: ConfigWriteBody,
    ) -> dict:
        try:
            return manager.write_soft_limits(
                subsystem,
                body.content,
                body.revision,
            )
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.post("/jobs", status_code=status.HTTP_201_CREATED)
    def create_job(body: JobCreateBody) -> dict:
        try:
            return manager.create_job(
                body.subsystem,
                body.operation,
                body.motor_ids,
            )
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        try:
            return manager.get_job(job_id)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.post("/jobs/{job_id}/confirm")
    def confirm_job(job_id: str) -> dict:
        """Confirm only the currently waiting motor is free to spin."""
        try:
            return manager.confirm_job(job_id)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        try:
            return manager.cancel_job(job_id)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str) -> dict:
        try:
            return manager.retry_job(job_id)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    @router.post("/jobs/{job_id}/skip")
    def skip_job_item(job_id: str) -> dict:
        try:
            return manager.skip_job_item(job_id)
        except CommissioningError as exc:
            raise_commissioning_http(exc)

    return router


def create_legacy_commissioning_router(
    manager: CommissioningManager,
) -> APIRouter:
    """Keep the old one-wheel route while executing through the job model."""
    router = APIRouter(
        prefix="/api/drive",
        tags=["commissioning-compatibility"],
        dependencies=[Depends(require_commissioning_access)],
    )

    @router.post("/calibrate/{wheel}")
    async def calibrate_wheel(wheel: str, body: CalibrationRequest) -> dict:
        if not body.off_ground_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="off-ground confirmation is required for this wheel",
            )

        try:
            job = manager.create_job("core", "calibrate", [wheel.lower()])
            manager.confirm_job(job["id"])
        except CommissioningError as exc:
            raise_commissioning_http(exc)

        try:
            terminal_job = await asyncio.to_thread(
                manager.wait_for_terminal_or_failure,
                job["id"],
                300.0,
            )
        except CommissioningStateError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc

        # The old route has no browser job dialog through which an operator can
        # retry. End its failed one-motor job immediately so it cannot retain
        # the global commissioning interlock for five minutes.
        if terminal_job["state"] == "failed":
            terminal_job = manager.cancel_job(job["id"])

        item = terminal_job["items"][0]
        return {
            "ok": terminal_job["state"] == "succeeded",
            "message": item["message"],
            "job_id": terminal_job["id"],
        }

    return router
