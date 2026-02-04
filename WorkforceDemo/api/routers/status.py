"""
Status router - Status monitoring and WebSocket endpoints.

Provides endpoints for:
- Fleet status
- Real-time WebSocket updates
- Health check
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

from ..models import FleetStatusResponse, DroneStatusResponse
from ..services import get_drone_service, get_safety_service
from ..config import settings

router = APIRouter(prefix="/status", tags=["Status"])


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


def get_services():
    """Get service instances."""
    return get_drone_service(), get_safety_service()


# =========================================================================
# Status Endpoints
# =========================================================================

@router.get(
    "/health",
    summary="Health check",
    description="Check if the API is running and connected to AirSim."
)
async def health_check():
    """Health check endpoint."""
    drone_service, _ = get_services()
    return {
        "status": "healthy",
        "airsim_connected": drone_service.is_connected,
        "version": settings.app_version
    }


@router.get(
    "/fleet",
    response_model=FleetStatusResponse,
    summary="Get fleet status",
    description="Get current status of all drones including positions, states, and tasks."
)
async def get_fleet_status():
    """Get status of all drones."""
    drone_service, safety_service = get_services()

    statuses = drone_service.get_fleet_status()
    drone_responses = [DroneStatusResponse(**s.to_dict()) for s in statuses]

    flying_states = ['flying', 'taking_off', 'landing']
    flying_count = sum(1 for s in statuses if s.state.value in flying_states)

    return FleetStatusResponse(
        drones=drone_responses,
        total_count=len(statuses),
        flying_count=flying_count,
        emergency_active=safety_service.is_emergency_active()
    )


@router.get(
    "/positions",
    summary="Get all drone positions",
    description="Get simplified position data for all drones."
)
async def get_all_positions():
    """Get positions of all drones."""
    drone_service, _ = get_services()
    positions = drone_service.get_all_positions()

    return {
        "positions": {
            drone_id: {"x": pos[0], "y": pos[1], "z": pos[2], "altitude": -pos[2]}
            for drone_id, pos in positions.items()
        }
    }


@router.get(
    "/collision-risks",
    summary="Check collision risks",
    description="Check for potential collision risks between drones."
)
async def check_collision_risks():
    """Check for collision risks."""
    _, safety_service = get_services()
    risks = safety_service.check_collision_risks()
    return {
        "risks": risks,
        "count": len(risks),
        "has_critical": any(r["severity"] == "critical" for r in risks)
    }


# =========================================================================
# WebSocket Endpoint
# =========================================================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time status updates.

    Connects to receive 1Hz updates of fleet status.
    """
    await manager.connect(websocket)

    drone_service, safety_service = get_services()

    try:
        while True:
            # Build status update
            try:
                statuses = drone_service.get_fleet_status()
                flying_states = ['flying', 'taking_off', 'landing']
                flying_count = sum(1 for s in statuses if s.state.value in flying_states)

                update = {
                    "drones": [s.to_dict() for s in statuses],
                    "total_count": len(statuses),
                    "flying_count": flying_count,
                    "emergency_active": safety_service.is_emergency_active()
                }

                await websocket.send_json(update)

            except Exception as e:
                # If not connected to AirSim, send empty status
                await websocket.send_json({
                    "drones": [],
                    "total_count": 0,
                    "flying_count": 0,
                    "emergency_active": False,
                    "error": str(e)
                })

            # Wait for next update interval
            await asyncio.sleep(settings.ws_update_interval)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get(
    "/ws-clients",
    summary="Get WebSocket client count",
    description="Get the number of connected WebSocket clients."
)
async def get_ws_clients():
    """Get number of connected WebSocket clients."""
    return {"connected_clients": len(manager.active_connections)}
