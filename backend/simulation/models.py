"""Data models and schemas for HomeMind Home Simulation."""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class GlobalHomeState(str, Enum):
    """Global home states defined in the HomeMind specification."""
    HOME = "HOME"
    AWAY = "AWAY"
    SLEEP = "SLEEP"
    MORNING = "MORNING"
    EMERGENCY = "EMERGENCY"
    MAINTENANCE = "MAINTENANCE"


class DeviceType(str, Enum):
    """Supported smart home device types."""
    LIGHT = "LIGHT"
    AC = "AC"
    FAN = "FAN"
    TV = "TV"
    REFRIGERATOR = "REFRIGERATOR"
    SMART_LOCK = "SMART_LOCK"
    WATER_TANK = "WATER_TANK"
    WATER_PUMP = "WATER_PUMP"
    MOTION_SENSOR = "MOTION_SENSOR"
    DOOR_SENSOR = "DOOR_SENSOR"


class DevicePowerState(str, Enum):
    """Operating states of smart devices."""
    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"
    FAULT = "FAULT"


class DoorState(str, Enum):
    """Door sensor physical state."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"


class LockState(str, Enum):
    """Smart lock physical state."""
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"


class DeviceState(BaseModel):
    """State representation for a single device in the home."""
    id: str
    name: str
    room_id: str
    device_type: DeviceType
    power_state: DevicePowerState = DevicePowerState.OFF
    power_draw_watts: float = 0.0
    attributes: Dict[str, object] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class RoomEnvironment(BaseModel):
    """Environmental sensor readings for a specific room."""
    room_id: str
    room_name: str
    temperature_celsius: float = 26.0
    humidity_percent: float = 55.0
    motion_detected: bool = False
    occupied: bool = False
    light_level_lux: float = 200.0


class WaterSystemState(BaseModel):
    """Water tank and plumbing telemetry."""
    tank_capacity_liters: float = 1000.0
    current_water_liters: float = 750.0
    water_level_percent: float = 75.0
    pump_active: bool = False
    flow_rate_lpm: float = 0.0  # liters per minute
    leak_rate_lpm: float = 0.0  # liters per minute simulated leakage


class EnergySystemState(BaseModel):
    """Aggregate electrical telemetry."""
    instant_power_watts: float = 0.0
    instant_power_kw: float = 0.0
    daily_energy_kwh: float = 0.0
    peak_draw_watts: float = 0.0


class SecuritySystemState(BaseModel):
    """Security perimeter and access telemetry."""
    entrance_door_state: DoorState = DoorState.CLOSED
    entrance_lock_state: LockState = LockState.LOCKED
    window_open: bool = False
    away_mode_armed: bool = False
    security_alerts_count: int = 0


class SimulationEvent(BaseModel):
    """Logged event from the simulation engine."""
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str  # e.g. "sensor.door", "device.ac", "environment"
    event_type: str  # e.g. "MOTION_DETECTED", "DOOR_OPENED", "WATER_SPIKE"
    description: str
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    data: Dict[str, object] = Field(default_factory=dict)


class HomeStateSnapshot(BaseModel):
    """Complete snapshot of the home digital twin at a point in time."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    simulation_time_str: str = "07:00 AM"
    global_home_state: GlobalHomeState = GlobalHomeState.HOME
    outdoor_temperature_celsius: float = 32.0
    outdoor_humidity_percent: float = 60.0
    rooms: Dict[str, RoomEnvironment] = Field(default_factory=dict)
    devices: Dict[str, DeviceState] = Field(default_factory=dict)
    water_system: WaterSystemState = Field(default_factory=WaterSystemState)
    energy_system: EnergySystemState = Field(default_factory=EnergySystemState)
    security_system: SecuritySystemState = Field(default_factory=SecuritySystemState)
    recent_events: List[SimulationEvent] = Field(default_factory=list)

