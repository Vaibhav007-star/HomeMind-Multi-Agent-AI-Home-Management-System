"""Device controllers and appliances implementation for HomeMind."""

from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime
from backend.simulation.models import (
    DeviceState,
    DeviceType,
    DevicePowerState,
    LockState,
    DoorState
)


class SmartDevice:
    """Base class for all simulated home appliances and devices."""

    def __init__(
        self,
        device_id: str,
        name: str,
        room_id: str,
        device_type: DeviceType,
        standby_watts: float = 2.0,
        active_watts: float = 50.0
    ):
        self.device_id = device_id
        self.name = name
        self.room_id = room_id
        self.device_type = device_type
        self.standby_watts = standby_watts
        self.active_watts = active_watts
        self.power_state = DevicePowerState.OFF
        self.attributes: Dict[str, Any] = {}
        self.last_updated = datetime.utcnow()

    def turn_on(self) -> None:
        self.power_state = DevicePowerState.ON
        self.last_updated = datetime.utcnow()

    def turn_off(self) -> None:
        self.power_state = DevicePowerState.OFF
        self.last_updated = datetime.utcnow()

    def set_standby(self) -> None:
        self.power_state = DevicePowerState.STANDBY
        self.last_updated = datetime.utcnow()

    def get_current_power_draw(self) -> float:
        """Calculate dynamic wattage based on operating state."""
        if self.power_state == DevicePowerState.OFF:
            return 0.0
        elif self.power_state == DevicePowerState.STANDBY:
            return self.standby_watts
        elif self.power_state == DevicePowerState.ON:
            return self.active_watts
        return 0.0

    def to_state_model(self) -> DeviceState:
        return DeviceState(
            id=self.device_id,
            name=self.name,
            room_id=self.room_id,
            device_type=self.device_type,
            power_state=self.power_state,
            power_draw_watts=self.get_current_power_draw(),
            attributes=dict(self.attributes),
            last_updated=self.last_updated
        )


class SmartLight(SmartDevice):
    """Simulated smart LED bulb with brightness level."""

    def __init__(self, device_id: str, name: str, room_id: str, max_watts: float = 15.0):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.LIGHT,
            standby_watts=0.5,
            active_watts=max_watts
        )
        self.attributes["brightness"] = 100  # 0 to 100%

    def set_brightness(self, level: int) -> None:
        self.attributes["brightness"] = max(0, min(100, level))
        if self.attributes["brightness"] == 0:
            self.turn_off()
        else:
            self.turn_on()

    def get_current_power_draw(self) -> float:
        if self.power_state != DevicePowerState.ON:
            return super().get_current_power_draw()
        brightness = self.attributes.get("brightness", 100)
        # Power scales with brightness
        return round(self.active_watts * (brightness / 100.0) + self.standby_watts, 2)


class AirConditioner(SmartDevice):
    """Simulated inverter Air Conditioner with thermostat control."""

    def __init__(self, device_id: str, name: str, room_id: str):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.AC,
            standby_watts=5.0,
            active_watts=1400.0
        )
        self.attributes["target_temp_celsius"] = 24.0
        self.attributes["mode"] = "cool"  # cool, fan, eco
        self.attributes["compressor_active"] = False

    def set_target_temperature(self, temp_celsius: float) -> None:
        self.attributes["target_temp_celsius"] = round(float(temp_celsius), 1)
        self.last_updated = datetime.utcnow()

    def set_mode(self, mode: str) -> None:
        if mode in ["cool", "fan", "eco"]:
            self.attributes["mode"] = mode
            self.last_updated = datetime.utcnow()

    def update_compressor(self, current_room_temp: float) -> None:
        """Determines compressor activity based on room temperature vs target setpoint."""
        if self.power_state != DevicePowerState.ON:
            self.attributes["compressor_active"] = False
            return

        target = self.attributes.get("target_temp_celsius", 24.0)
        # Inverter compressor turns on when indoor temp is above target
        if current_room_temp > target + 0.3:
            self.attributes["compressor_active"] = True
        elif current_room_temp <= target - 0.2:
            self.attributes["compressor_active"] = False

    def get_current_power_draw(self) -> float:
        if self.power_state != DevicePowerState.ON:
            return super().get_current_power_draw()

        compressor = self.attributes.get("compressor_active", False)
        mode = self.attributes.get("mode", "cool")

        if mode == "fan":
            return 45.0
        elif mode == "eco":
            return 900.0 if compressor else 40.0
        else:  # cool
            return self.active_watts if compressor else 50.0


class SmartFan(SmartDevice):
    """Simulated ceiling / standing fan with 3 speed settings."""

    def __init__(self, device_id: str, name: str, room_id: str):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.FAN,
            standby_watts=1.0,
            active_watts=50.0
        )
        self.attributes["speed"] = 2  # 1 (low), 2 (med), 3 (high)

    def set_speed(self, speed: int) -> None:
        self.attributes["speed"] = max(1, min(3, speed))
        self.turn_on()

    def get_current_power_draw(self) -> float:
        if self.power_state != DevicePowerState.ON:
            return super().get_current_power_draw()
        speed = self.attributes.get("speed", 2)
        power_map = {1: 30.0, 2: 50.0, 3: 75.0}
        return power_map.get(speed, 50.0)


class Television(SmartDevice):
    """Simulated Smart TV."""

    def __init__(self, device_id: str, name: str, room_id: str):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.TV,
            standby_watts=2.0,
            active_watts=120.0
        )


class Refrigerator(SmartDevice):
    """Simulated Refrigerator with thermodynamic cooling cycles."""

    def __init__(self, device_id: str, name: str, room_id: str):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.REFRIGERATOR,
            standby_watts=15.0,
            active_watts=160.0
        )
        self.power_state = DevicePowerState.ON  # Refrigerator is always plugged in
        self.attributes["compressor_running"] = True
        self.cycle_counter = 0

    def tick_cycle(self) -> None:
        """Cycles compressor every few ticks to simulate realistic cycling."""
        self.cycle_counter += 1
        # Example: 30 mins cooling (active), 30 mins idle
        self.attributes["compressor_running"] = (self.cycle_counter % 6) < 3

    def get_current_power_draw(self) -> float:
        if self.power_state != DevicePowerState.ON:
            return 0.0
        if self.attributes.get("compressor_running", True):
            return self.active_watts
        return self.standby_watts


class SmartLock(SmartDevice):
    """Simulated front door electronic lock."""

    def __init__(self, device_id: str, name: str, room_id: str):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.SMART_LOCK,
            standby_watts=0.5,
            active_watts=5.0
        )
        self.power_state = DevicePowerState.ON
        self.attributes["lock_state"] = LockState.LOCKED.value
        self.attributes["last_unlocked_by"] = "PIN"

    def lock(self) -> None:
        self.attributes["lock_state"] = LockState.LOCKED.value
        self.last_updated = datetime.utcnow()

    def unlock(self, user_or_method: str = "Resident") -> None:
        self.attributes["lock_state"] = LockState.UNLOCKED.value
        self.attributes["last_unlocked_by"] = user_or_method
        self.last_updated = datetime.utcnow()

    def is_locked(self) -> bool:
        return self.attributes.get("lock_state") == LockState.LOCKED.value


class WaterPump(SmartDevice):
    """Simulated municipal/underground water pump to fill overhead tank."""

    def __init__(self, device_id: str, name: str, room_id: str):
        super().__init__(
            device_id=device_id,
            name=name,
            room_id=room_id,
            device_type=DeviceType.WATER_PUMP,
            standby_watts=1.0,
            active_watts=750.0
        )
        self.attributes["flow_rate_lpm"] = 25.0  # Fills 25 liters per minute when ON

