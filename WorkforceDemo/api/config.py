"""
Configuration settings for the drone API.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    app_name: str = "Drone Fleet API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000

    # AirSim Settings
    airsim_ip: str = "localhost"
    max_drones: int = 5

    # Safety Defaults
    default_altitude: float = 20.0
    max_altitude: float = 100.0
    min_altitude: float = 5.0
    default_speed: float = 5.0
    max_speed: float = 20.0

    # Geofence Defaults
    geofence_min_x: float = -100.0
    geofence_max_x: float = 100.0
    geofence_min_y: float = -100.0
    geofence_max_y: float = 100.0

    # WebSocket Settings
    ws_update_interval: float = 0.25  # seconds (4 updates/sec for smoother tracking)

    # File Paths
    house_labels_file: str = "house_labels.json"
    photo_directory: str = "house_photos"

    class Config:
        env_file = ".env"
        env_prefix = "DRONE_"


settings = Settings()
