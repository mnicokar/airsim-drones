"""
API routers package.
"""

from .drones import router as drones_router
from .fleet import router as fleet_router
from .status import router as status_router

__all__ = [
    "drones_router",
    "fleet_router",
    "status_router",
]
