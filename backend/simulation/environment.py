"""Physics and environmental dynamics engine for HomeMind."""

from __future__ import annotations
import math
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

from backend.simulation.models import (
    RoomEnvironment,
    WaterSystemState,
    EnergySystemState,
    SecuritySystemState,
    DoorState,
    LockState,
    DevicePowerState
)
from backend.simulation.devices import AirConditioner, WaterPump, SmartDevice


class EnvironmentEngine:
    """Simulates realistic thermal, electrical, hydraulic, and security physical dynamics."""

    def __init__(self):
        # Outdoor baseline weather
        self.outdoor_temp_celsius: float = 33.0
        self.outdoor_humidity_percent: float = 62.0
        self.solar_heat_gain: float = 1.0

        # Room thermal parameters
        # Natural thermal conduction coefficient towards outdoor temp (per minute)
        self.thermal_conductivity: float = 0.015
        # AC cooling power (°C reduction per minute under active compressor)
        self.ac_cooling_rate_per_min: float = 0.35

        # Water parameters
        self.water_tank_capacity_liters: float = 1000.0
        self.current_water_liters: float = 720.0
        self.simulated_leak_rate_lpm: float = 0.0  # 0 when no leak, >0 during leak scenario
        self.fixture_usage_lpm: float = 0.0

        # Energy tracking
        self.cumulative_energy_kwh: float = 4.2
        self.peak_draw_watts: float = 0.0

        # Security perimeter
        self.entrance_door_state: DoorState = DoorState.CLOSED
        self.entrance_lock_state: LockState = LockState.LOCKED
        self.window_open: bool = False
        self.away_mode_armed: bool = False

    def update_weather_by_time(self, hour: int, minute: int) -> None:
        """Computes diurnal outdoor temperature curve matching typical urban climate."""
        # Minimum at 5:30 AM (~24°C), maximum at 2:30 PM (~36°C)
        time_hours = hour + (minute / 60.0)
        # Shift sine wave so peak is at hour 14.5
        phase = (time_hours - 8.5) * (2 * math.pi / 24.0)
        base_temp = 30.0
        amplitude = 6.0  # Range: 24°C to 36°C
        self.outdoor_temp_celsius = round(base_temp + amplitude * math.sin(phase), 1)

        # Humidity is inversely related to temperature
        self.outdoor_humidity_percent = round(max(30.0, min(85.0, 75.0 - (self.outdoor_temp_celsius - 24.0) * 2.5)), 1)

    def simulate_room_thermodynamics(
        self,
        room: RoomEnvironment,
        associated_devices: List[SmartDevice],
        dt_minutes: float
    ) -> None:
        """Simulates heat exchange with the outside and active cooling appliances."""
        current_temp = room.temperature_celsius

        # Check if an AC is present in this room
        ac_devices = [d for d in associated_devices if isinstance(d, AirConditioner)]
        net_cooling = 0.0

        for ac in ac_devices:
            ac.update_compressor(current_temp)
            if ac.power_state == DevicePowerState.ON and ac.attributes.get("compressor_active", False):
                target = ac.attributes.get("target_temp_celsius", 24.0)
                if current_temp > target:
                    # AC actively removes heat
                    delta_cool = self.ac_cooling_rate_per_min * dt_minutes
                    # Don't overshoot target significantly
                    net_cooling += min(delta_cool, current_temp - target)

        # Natural heat transfer towards outdoor ambient
        heat_transfer = (self.outdoor_temp_celsius - current_temp) * self.thermal_conductivity * dt_minutes

        # Internal heat load from occupancy and lights
        internal_heat_load = 0.0
        if room.occupied:
            internal_heat_load += 0.02 * dt_minutes

        new_temp = current_temp + heat_transfer + internal_heat_load - net_cooling
        room.temperature_celsius = round(max(16.0, min(42.0, new_temp)), 1)

        # Humidity adjustment: AC dries out room slightly, unoccupied room drifts toward outdoor
        if net_cooling > 0.0:
            room.humidity_percent = max(38.0, room.humidity_percent - 0.2 * dt_minutes)
        else:
            room.humidity_percent += (self.outdoor_humidity_percent - room.humidity_percent) * 0.02 * dt_minutes
        room.humidity_percent = round(max(30.0, min(90.0, room.humidity_percent)), 1)

    def simulate_water_dynamics(
        self,
        pump: Optional[WaterPump],
        dt_minutes: float
    ) -> WaterSystemState:
        """Updates water tank levels, inflows from pump, and outflows from fixtures/leaks."""
        pump_active = False
        inflow_lpm = 0.0
        if pump and pump.power_state == DevicePowerState.ON:
            pump_active = True
            inflow_lpm = pump.attributes.get("flow_rate_lpm", 25.0)

        total_outflow_lpm = self.fixture_usage_lpm + self.simulated_leak_rate_lpm

        # Delta volume in liters
        delta_water = (inflow_lpm - total_outflow_lpm) * dt_minutes
        self.current_water_liters = max(0.0, min(self.water_tank_capacity_liters, self.current_water_liters + delta_water))

        # Auto-shutoff pump if tank reaches 98%
        if self.current_water_liters >= self.water_tank_capacity_liters * 0.98 and pump:
            pump.turn_off()
            pump_active = False

        water_percent = (self.current_water_liters / self.water_tank_capacity_liters) * 100.0

        return WaterSystemState(
            tank_capacity_liters=self.water_tank_capacity_liters,
            current_water_liters=round(self.current_water_liters, 1),
            water_level_percent=round(water_percent, 1),
            pump_active=pump_active,
            flow_rate_lpm=round(total_outflow_lpm, 2),
            leak_rate_lpm=round(self.simulated_leak_rate_lpm, 2)
        )

    def calculate_energy(
        self,
        devices: Dict[str, SmartDevice],
        dt_seconds: float
    ) -> EnergySystemState:
        """Aggregates real-time power draw and accumulates total consumption."""
        total_watts = 0.0
        for dev in devices.values():
            total_watts += dev.get_current_power_draw()

        total_watts = round(total_watts, 1)
        instant_kw = round(total_watts / 1000.0, 3)

        # Accumulate kWh
        hours = dt_seconds / 3600.0
        delta_kwh = (total_watts * hours) / 1000.0
        self.cumulative_energy_kwh = round(self.cumulative_energy_kwh + delta_kwh, 3)

        if total_watts > self.peak_draw_watts:
            self.peak_draw_watts = total_watts

        return EnergySystemState(
            instant_power_watts=total_watts,
            instant_power_kw=instant_kw,
            daily_energy_kwh=self.cumulative_energy_kwh,
            peak_draw_watts=self.peak_draw_watts
        )

    def get_security_state(self, alerts_count: int = 0) -> SecuritySystemState:
        return SecuritySystemState(
            entrance_door_state=self.entrance_door_state,
            entrance_lock_state=self.entrance_lock_state,
            window_open=self.window_open,
            away_mode_armed=self.away_mode_armed,
            security_alerts_count=alerts_count
        )
