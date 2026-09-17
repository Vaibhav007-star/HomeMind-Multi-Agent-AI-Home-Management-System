"""Unit and integration tests for HomeMind Core Home Simulation Engine (Phase 1)."""

import pytest
from backend.simulation.models import (
    GlobalHomeState,
    DevicePowerState,
    DoorState,
    LockState,
    DeviceType
)
from backend.simulation.simulator import HomeSimulator
from backend.simulation.devices import AirConditioner, SmartLight, SmartFan, Refrigerator


def test_simulator_initialization():
    """Verify that rooms, devices, and baseline state initialize properly."""
    sim = HomeSimulator(start_hour=7, start_minute=0)

    # Check rooms
    expected_rooms = ["living_room", "bedroom", "kitchen", "bathroom", "entrance"]
    for r in expected_rooms:
        assert r in sim.rooms
        assert sim.rooms[r].temperature_celsius > 15.0

    # Check devices
    assert "light_living" in sim.devices
    assert "ac_bedroom" in sim.devices
    assert "fridge_kitchen" in sim.devices
    assert "lock_entrance" in sim.devices
    assert "water_pump" in sim.devices

    # Check initial snapshot
    snapshot = sim.get_snapshot()
    assert snapshot.global_home_state == GlobalHomeState.HOME
    assert snapshot.simulation_time_str == "07:00 AM"
    assert snapshot.energy_system.instant_power_watts > 0.0


def test_device_control_and_power_draw():
    """Verify that toggling devices updates their power states and aggregate wattage."""
    sim = HomeSimulator()

    # Initial state
    initial_power = sim.get_snapshot().energy_system.instant_power_watts

    # Turn ON Living Room TV (120W)
    sim.set_device_power("tv_living", DevicePowerState.ON)
    power_with_tv = sim.get_snapshot().energy_system.instant_power_watts
    assert round(power_with_tv - initial_power, 1) == 120.0

    # Turn OFF Living Room TV
    sim.set_device_power("tv_living", DevicePowerState.OFF)
    power_tv_off = sim.get_snapshot().energy_system.instant_power_watts
    assert round(power_tv_off, 1) == round(initial_power, 1)

    # Test light brightness scaling
    light = sim.devices["light_living"]
    assert isinstance(light, SmartLight)
    sim.set_light_brightness("light_living", 50)
    p_50 = light.get_current_power_draw()
    sim.set_light_brightness("light_living", 100)
    p_100 = light.get_current_power_draw()
    assert p_100 > p_50


def test_thermodynamic_cooling_and_drift():
    """Verify realistic physics: AC cools the room; when AC is off, room drifts towards outdoor ambient."""
    sim = HomeSimulator(start_hour=14, start_minute=0)  # 2:00 PM (Hot afternoon)
    sim.env.outdoor_temp_celsius = 36.0

    bedroom = sim.rooms["bedroom"]
    bedroom.temperature_celsius = 30.0

    # Ensure AC is ON with target 23°C
    sim.set_device_power("ac_bedroom", DevicePowerState.ON)
    sim.set_ac_target("ac_bedroom", 23.0)

    # Tick for 10 minutes
    for _ in range(10):
        sim.tick(delta_seconds=60)

    # Temperature should have cooled down
    assert sim.rooms["bedroom"].temperature_celsius < 30.0
    cooled_temp = sim.rooms["bedroom"].temperature_celsius

    # Now turn AC OFF
    sim.set_device_power("ac_bedroom", DevicePowerState.OFF)

    # Tick for another 15 minutes in the hot afternoon
    for _ in range(15):
        sim.tick(delta_seconds=60)

    # Temperature should have warmed up towards outdoor ambient
    assert sim.rooms["bedroom"].temperature_celsius > cooled_temp


def test_water_plumbing_and_leak_simulation():
    """Verify water consumption, pump refill, and abnormal leakage dynamics."""
    sim = HomeSimulator()
    initial_liters = sim.env.current_water_liters

    # Inject simulated leak of 4.0 LPM
    sim.set_water_leak(True, leak_rate_lpm=4.0)

    # Advance 5 minutes
    for _ in range(5):
        sim.tick(delta_seconds=60)

    # Water should have decreased by ~20 Liters (4 LPM * 5 min)
    assert sim.env.current_water_liters < initial_liters
    assert round(initial_liters - sim.env.current_water_liters, 0) == 20.0

    # Clear leak and turn ON pump
    sim.set_water_leak(False)
    sim.set_device_power("water_pump", DevicePowerState.ON)
    post_leak_liters = sim.env.current_water_liters

    # Advance 2 minutes (Pump fills at 25 LPM = +50 Liters)
    for _ in range(2):
        sim.tick(delta_seconds=60)

    assert sim.env.current_water_liters > post_leak_liters
    assert round(sim.env.current_water_liters - post_leak_liters, 0) == 50.0


def test_security_perimeter_states():
    """Verify smart lock, door sensor, and away mode alert tracking."""
    sim = HomeSimulator()

    # Front door state changes
    sim.set_door_state(True)
    assert sim.env.entrance_door_state == DoorState.OPEN
    sim.set_door_state(False)
    assert sim.env.entrance_door_state == DoorState.CLOSED

    # Smart lock changes
    sim.set_lock_state(False)
    assert sim.env.entrance_lock_state == LockState.UNLOCKED
    sim.set_lock_state(True)
    assert sim.env.entrance_lock_state == LockState.LOCKED


def test_scenarios_setup():
    """Verify that helper methods configure the 3 primary scenarios properly."""
    sim = HomeSimulator()

    # Scenario 1: Morning Routine
    sim.trigger_scenario_morning()
    assert sim.global_home_state == GlobalHomeState.MORNING
    assert sim.rooms["bedroom"].occupied is True
    assert sim.sim_time.hour == 7

    # Scenario 2: Leaving Home
    sim.trigger_scenario_leaving()
    assert sim.global_home_state == GlobalHomeState.AWAY
    assert sim.env.away_mode_armed is True
    assert all(not r.occupied for r in sim.rooms.values())

    # Scenario 3: Abnormal Water Usage
    sim.trigger_scenario_water_leak()
    assert sim.global_home_state == GlobalHomeState.AWAY
    assert sim.env.simulated_leak_rate_lpm > 0.0
    snapshot = sim.tick(delta_seconds=60)
    assert snapshot.security_system.security_alerts_count > 0


def test_snapshot_json_serialization():
    """Verify snapshot serializes cleanly into JSON/dictionary format for frontend/API."""
    sim = HomeSimulator()
    snapshot = sim.get_snapshot()

    data = snapshot.model_dump()
    assert "rooms" in data
    assert "devices" in data
    assert "water_system" in data
    assert "energy_system" in data
    assert "security_system" in data
    assert data["global_home_state"] == "HOME"

    json_str = snapshot.model_dump_json()
    assert isinstance(json_str, str)
    assert len(json_str) > 100

