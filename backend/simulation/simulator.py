"""Digital Twin Home Simulator for HomeMind."""

from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

from backend.simulation.models import (
    GlobalHomeState,
    DeviceType,
    DevicePowerState,
    DoorState,
    LockState,
    RoomEnvironment,
    DeviceState,
    WaterSystemState,
    EnergySystemState,
    SimulationEvent,
    HomeStateSnapshot
)
from backend.simulation.devices import (
    SmartDevice,
    SmartLight,
    AirConditioner,
    SmartFan,
    Television,
    Refrigerator,
    SmartLock,
    WaterPump
)
from backend.simulation.environment import EnvironmentEngine


class HomeSimulator:
    """Core Digital Twin simulation engine for the urban home environment."""

    def __init__(self, start_hour: int = 7, start_minute: int = 0):
        # Simulation clock
        self.sim_time = datetime(2026, 9, 17, start_hour, start_minute, 0)
        self.global_home_state = GlobalHomeState.HOME

        # Environment & Physics
        self.env = EnvironmentEngine()
        self.env.update_weather_by_time(self.sim_time.hour, self.sim_time.minute)

        # Rooms
        self.rooms: Dict[str, RoomEnvironment] = {
            "living_room": RoomEnvironment(room_id="living_room", room_name="Living Room", temperature_celsius=27.5, humidity_percent=56.0, occupied=True, motion_detected=True),
            "bedroom": RoomEnvironment(room_id="bedroom", room_name="Bedroom", temperature_celsius=25.0, humidity_percent=52.0, occupied=True, motion_detected=False),
            "kitchen": RoomEnvironment(room_id="kitchen", room_name="Kitchen", temperature_celsius=28.0, humidity_percent=58.0, occupied=False, motion_detected=False),
            "bathroom": RoomEnvironment(room_id="bathroom", room_name="Bathroom", temperature_celsius=27.0, humidity_percent=65.0, occupied=False, motion_detected=False),
            "entrance": RoomEnvironment(room_id="entrance", room_name="Entrance", temperature_celsius=29.0, humidity_percent=58.0, occupied=False, motion_detected=False),
        }

        # Devices
        self.devices: Dict[str, SmartDevice] = {}
        self._init_default_devices()

        # Event stream
        self.events: List[SimulationEvent] = []
        self._log_event("simulator", "SYSTEM_START", "HomeMind Digital Twin Simulation Initialized", "INFO")

    def _init_default_devices(self) -> None:
        """Initializes all standard urban home devices across rooms."""
        # Living Room
        self.devices["light_living"] = SmartLight("light_living", "Living Room Main Light", "living_room", max_watts=20.0)
        self.devices["ac_living"] = AirConditioner("ac_living", "Living Room AC", "living_room")
        self.devices["fan_living"] = SmartFan("fan_living", "Living Room Ceiling Fan", "living_room")
        self.devices["tv_living"] = Television("tv_living", "Living Room Smart TV", "living_room")

        # Bedroom
        self.devices["light_bedroom"] = SmartLight("light_bedroom", "Bedroom Light", "bedroom", max_watts=15.0)
        self.devices["ac_bedroom"] = AirConditioner("ac_bedroom", "Bedroom AC", "bedroom")
        self.devices["fan_bedroom"] = SmartFan("fan_bedroom", "Bedroom Fan", "bedroom")

        # Kitchen
        self.devices["light_kitchen"] = SmartLight("light_kitchen", "Kitchen Light", "kitchen", max_watts=18.0)
        self.devices["fridge_kitchen"] = Refrigerator("fridge_kitchen", "Smart Inverter Refrigerator", "kitchen")

        # Bathroom
        self.devices["light_bathroom"] = SmartLight("light_bathroom", "Bathroom Light", "bathroom", max_watts=12.0)

        # Entrance
        self.devices["light_entrance"] = SmartLight("light_entrance", "Entrance Porch Light", "entrance", max_watts=10.0)
        self.devices["lock_entrance"] = SmartLock("lock_entrance", "Main Entrance Smart Lock", "entrance")

        # Utility
        self.devices["water_pump"] = WaterPump("water_pump", "Overhead Water Tank Pump", "bathroom")

        # Initial device states for 7:00 AM baseline
        self.devices["ac_bedroom"].turn_on()
        self.devices["ac_bedroom"].set_target_temperature(23.0)
        self.devices["fan_bedroom"].turn_on()
        self.devices["light_living"].turn_on()

    def _log_event(self, source: str, event_type: str, description: str, severity: str = "INFO", data: Optional[dict] = None) -> None:
        event = SimulationEvent(
            id=str(uuid.uuid4())[:8],
            timestamp=self.sim_time,
            source=source,
            event_type=event_type,
            description=description,
            severity=severity,
            data=data or {}
        )
        self.events.append(event)
        # Keep last 100 events in memory
        if len(self.events) > 100:
            self.events.pop(0)

    # Device Controls
    def set_device_power(self, device_id: str, power_state: DevicePowerState) -> bool:
        if device_id not in self.devices:
            return False
        dev = self.devices[device_id]
        if power_state == DevicePowerState.ON:
            dev.turn_on()
        elif power_state == DevicePowerState.OFF:
            dev.turn_off()
        elif power_state == DevicePowerState.STANDBY:
            dev.set_standby()

        self._log_event(f"device.{device_id}", "POWER_CHANGE", f"{dev.name} set to {power_state.value}", "INFO")
        return True

    def set_ac_target(self, device_id: str, target_celsius: float) -> bool:
        if device_id in self.devices and isinstance(self.devices[device_id], AirConditioner):
            ac: AirConditioner = self.devices[device_id] # type: ignore
            ac.set_target_temperature(target_celsius)
            self._log_event(f"device.{device_id}", "AC_TARGET_CHANGED", f"{ac.name} target set to {target_celsius}°C", "INFO")
            return True
        return False

    def set_light_brightness(self, device_id: str, brightness_percent: int) -> bool:
        if device_id in self.devices and isinstance(self.devices[device_id], SmartLight):
            light: SmartLight = self.devices[device_id] # type: ignore
            light.set_brightness(brightness_percent)
            return True
        return False

    def set_fan_speed(self, device_id: str, speed: int) -> bool:
        if device_id in self.devices and isinstance(self.devices[device_id], SmartFan):
            fan: SmartFan = self.devices[device_id] # type: ignore
            fan.set_speed(speed)
            return True
        return False

    def set_door_state(self, open_state: bool) -> None:
        new_state = DoorState.OPEN if open_state else DoorState.CLOSED
        if self.env.entrance_door_state != new_state:
            self.env.entrance_door_state = new_state
            severity = "WARNING" if (self.global_home_state == GlobalHomeState.AWAY and open_state) else "INFO"
            self._log_event("sensor.door", "DOOR_TRANSITION", f"Front door {new_state.value}", severity)

    def set_lock_state(self, locked: bool) -> None:
        new_state = LockState.LOCKED if locked else LockState.UNLOCKED
        self.env.entrance_lock_state = new_state
        lock = self.devices.get("lock_entrance")
        if lock and isinstance(lock, SmartLock):
            if locked:
                lock.lock()
            else:
                lock.unlock()
        self._log_event("device.lock", "LOCK_TRANSITION", f"Smart lock {new_state.value}", "INFO")

    def set_occupancy(self, room_id: str, occupied: bool) -> None:
        if room_id in self.rooms:
            room = self.rooms[room_id]
            room.occupied = occupied
            room.motion_detected = occupied
            if occupied:
                self._log_event(f"sensor.motion.{room_id}", "MOTION_DETECTED", f"Motion detected in {room.room_name}", "INFO")

    def set_water_leak(self, active: bool, leak_rate_lpm: float = 3.5) -> None:
        self.env.simulated_leak_rate_lpm = leak_rate_lpm if active else 0.0
        if active:
            self._log_event("plumbing.sensor", "LEAK_INJECTED", f"Simulated water leak initiated at {leak_rate_lpm} L/min", "WARNING")
        else:
            self._log_event("plumbing.sensor", "LEAK_CLEARED", "Simulated water leak cleared", "INFO")

    def set_fixture_usage(self, flow_rate_lpm: float) -> None:
        self.env.fixture_usage_lpm = max(0.0, flow_rate_lpm)

    def set_global_home_state(self, state: GlobalHomeState) -> None:
        old_state = self.global_home_state
        self.global_home_state = state
        self.env.away_mode_armed = (state == GlobalHomeState.AWAY)
        self._log_event("home_manager", "STATE_CHANGED", f"Global Home State changed from {old_state.value} to {state.value}", "INFO")

    # Simulation Advance (Tick)
    def tick(self, delta_seconds: int = 60) -> HomeStateSnapshot:
        """Advances the digital twin physics and state by delta_seconds (default 1 min)."""
        dt_minutes = delta_seconds / 60.0
        self.sim_time += timedelta(seconds=delta_seconds)

        # 1. Update weather curve
        self.env.update_weather_by_time(self.sim_time.hour, self.sim_time.minute)

        # 2. Cycle continuous appliances
        fridge = self.devices.get("fridge_kitchen")
        if isinstance(fridge, Refrigerator):
            fridge.tick_cycle()

        # 3. Simulate room thermal physics
        for room_id, room in self.rooms.items():
            room_devs = [d for d in self.devices.values() if d.room_id == room_id]
            self.env.simulate_room_thermodynamics(room, room_devs, dt_minutes)

        # 4. Simulate water plumbing & tank
        pump = self.devices.get("water_pump")
        water_state = self.env.simulate_water_dynamics(pump if isinstance(pump, WaterPump) else None, dt_minutes)

        # 5. Aggregate energy telemetry
        energy_state = self.env.calculate_energy(self.devices, delta_seconds)

        # 6. Check for automatic alerts
        alerts_count = 0
        if self.global_home_state == GlobalHomeState.AWAY and self.env.entrance_door_state == DoorState.OPEN:
            alerts_count += 1
        if self.global_home_state == GlobalHomeState.AWAY and water_state.flow_rate_lpm > 1.0:
            alerts_count += 1

        return self.get_snapshot(alerts_count)

    # Primary Demonstration Scenario Setup Helpers (Per Section 8)
    def trigger_scenario_morning(self) -> None:
        """Sets up Scenario 1: Morning Routine (07:00 AM)."""
        self.sim_time = datetime(2026, 9, 17, 7, 0, 0)
        self.set_global_home_state(GlobalHomeState.MORNING)
        self.set_occupancy("bedroom", True)
        self.set_occupancy("living_room", False)
        self.set_occupancy("kitchen", False)
        self.set_occupancy("bathroom", False)
        self.set_occupancy("entrance", False)
        self.env.entrance_door_state = DoorState.CLOSED
        self.env.entrance_lock_state = LockState.LOCKED
        self.set_water_leak(False)
        self.set_fixture_usage(2.0)  # Morning bathroom tap
        self._log_event("scenario", "SCENARIO_MORNING_TRIGGERED", "Scenario 1: Morning Routine initiated at 7:00 AM", "INFO")

    def trigger_scenario_leaving(self) -> None:
        """Sets up Scenario 2: Leaving Home (Transition to AWAY)."""
        self.sim_time = datetime(2026, 9, 17, 8, 30, 0)
        self.set_global_home_state(GlobalHomeState.AWAY)
        # All rooms become unoccupied
        for r_id in self.rooms:
            self.set_occupancy(r_id, False)
        self.set_door_state(True)  # Resident opened door to leave
        self.set_door_state(False)  # Door closed
        self.set_lock_state(True)   # Door locked
        self.set_water_leak(False)
        self.set_fixture_usage(0.0)
        self._log_event("scenario", "SCENARIO_LEAVING_TRIGGERED", "Scenario 2: Resident Leaving Home initiated", "INFO")

    def trigger_scenario_water_leak(self) -> None:
        """Sets up Scenario 3: Abnormal Water Usage while AWAY."""
        self.sim_time = datetime(2026, 9, 17, 11, 15, 0)
        self.set_global_home_state(GlobalHomeState.AWAY)
        # Nobody home
        for r_id in self.rooms:
            self.set_occupancy(r_id, False)
        self.set_door_state(False)
        self.set_lock_state(True)
        self.set_fixture_usage(0.0)
        # Inject leakage
        self.set_water_leak(True, leak_rate_lpm=4.2)
        self._log_event("scenario", "SCENARIO_WATER_LEAK_TRIGGERED", "Scenario 3: Abnormal Water Usage while AWAY initiated", "WARNING")

    def get_snapshot(self, alerts_count: int = 0) -> HomeStateSnapshot:
        """Returns serializable digital-twin state snapshot."""
        devices_dict: Dict[str, DeviceState] = {
            dev_id: dev.to_state_model() for dev_id, dev in self.devices.items()
        }

        water_state = WaterSystemState(
            tank_capacity_liters=self.env.water_tank_capacity_liters,
            current_water_liters=round(self.env.current_water_liters, 1),
            water_level_percent=round((self.env.current_water_liters / self.env.water_tank_capacity_liters) * 100.0, 1),
            pump_active=self.devices.get("water_pump").power_state == DevicePowerState.ON if "water_pump" in self.devices else False,
            flow_rate_lpm=round(self.env.fixture_usage_lpm + self.env.simulated_leak_rate_lpm, 2),
            leak_rate_lpm=round(self.env.simulated_leak_rate_lpm, 2)
        )

        energy_state = EnergySystemState(
            instant_power_watts=round(sum(d.get_current_power_draw() for d in self.devices.values()), 1),
            instant_power_kw=round(sum(d.get_current_power_draw() for d in self.devices.values()) / 1000.0, 3),
            daily_energy_kwh=self.env.cumulative_energy_kwh,
            peak_draw_watts=self.env.peak_draw_watts
        )

        security_state = self.env.get_security_state(alerts_count)

        return HomeStateSnapshot(
            timestamp=self.sim_time,
            simulation_time_str=self.sim_time.strftime("%I:%M %p"),
            global_home_state=self.global_home_state,
            outdoor_temperature_celsius=self.env.outdoor_temp_celsius,
            outdoor_humidity_percent=self.env.outdoor_humidity_percent,
            rooms={r_id: r.model_copy() for r_id, r in self.rooms.items()},
            devices=devices_dict,
            water_system=water_state,
            energy_system=energy_state,
            security_system=security_state,
            recent_events=list(self.events[-15:])
        )
