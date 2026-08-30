"""Small HTTP facade over the separate onboard ROS launch agent."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .pin_auth import is_pin_configured


def require_launch_access(request: Request) -> None:
    """Require the existing operator PIN session when one is configured."""
    if is_pin_configured() and request.session.get("pin_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN authentication is required for system startup",
        )


def _raise_launch_http(result: dict) -> None:
    if result.get("error") == "unavailable":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_409_CONFLICT
    raise HTTPException(
        status_code=status_code,
        detail=result.get("message") or "launch request failed",
    )


def create_launch_router(runtime) -> APIRouter:
    """Create fixed lifecycle routes around an injected ROS runtime."""
    router = APIRouter(
        prefix="/api/systems",
        tags=["system-startup"],
        dependencies=[Depends(require_launch_access)],
    )

    @router.get("")
    async def list_systems() -> dict:
        result = await asyncio.to_thread(runtime.list_managed_launches)
        if not result.get("ok"):
            _raise_launch_http(result)
        return {"systems": result.get("systems", [])}

    async def change(system_id: str, action: str) -> dict:
        result = await asyncio.to_thread(
            runtime.change_managed_launch,
            system_id,
            action,
        )
        if not result.get("ok"):
            _raise_launch_http(result)
        return result["system"]

    @router.post("/{system_id}/start")
    async def start_system(system_id: str) -> dict:
        return await change(system_id, "start")

    @router.post("/{system_id}/stop")
    async def stop_system(system_id: str) -> dict:
        return await change(system_id, "stop")

    @router.post("/{system_id}/restart")
    async def restart_system(system_id: str) -> dict:
        return await change(system_id, "restart")

    return router
