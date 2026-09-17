"""Interactive command-line demonstration of the HomeMind Digital Twin Simulator."""

import time
from backend.simulation import HomeSimulator, DevicePowerState, GlobalHomeState


def print_separator(title: str = ""):
    print("\n" + "=" * 65)
    if title:
        print(f"   {title}")
        print("=" * 65)


def print_telemetry(sim: HomeSimulator):
    snap = sim.get_snapshot()
    print(f"\n--- [Sim Time: {snap.simulation_time_str} | Mode: {snap.global_home_state.value}] ---")
    print(f"Outdoor Weather: {snap.outdoor_temperature_celsius}°C, {snap.outdoor_humidity_percent}% humidity")
    print(f"Instant Power  : {snap.energy_system.instant_power_watts} W ({snap.energy_system.instant_power_kw} kW) | Daily: {snap.energy_system.daily_energy_kwh} kWh | Peak: {snap.energy_system.peak_draw_watts} W")
    print(f"Water Tank     : {snap.water_system.current_water_liters} L ({snap.water_system.water_level_percent}%) | Flow: {snap.water_system.flow_rate_lpm} L/min (Leak: {snap.water_system.leak_rate_lpm} L/min)")
    print(f"Security       : Door {snap.security_system.entrance_door_state.value} | Lock {snap.security_system.entrance_lock_state.value} | Armed: {snap.security_system.away_mode_armed}")
    
    print("\nRoom Status:")
    for r_id, r in snap.rooms.items():
        occ = "Occupied" if r.occupied else "Vacant"
        print(f"  * {r.room_name:<14}: {r.temperature_celsius}°C, {r.humidity_percent}% RH | {occ}")


def run_demo():
    print_separator("HomeMind — Phase 1: Core Digital Twin Simulation Demo")
    sim = HomeSimulator(start_hour=7, start_minute=0)
    print_telemetry(sim)

    # 1. Device manipulation
    print_separator("ACTION: Resident turns on Living Room TV and Kitchen Light")
    sim.set_device_power("tv_living", DevicePowerState.ON)
    sim.set_device_power("light_kitchen", DevicePowerState.ON)
    sim.tick(delta_seconds=60)
    print_telemetry(sim)

    # 2. Thermodynamic Cooling
    print_separator("ACTION: Bedroom AC running at 22°C setpoint for 5 simulated minutes")
    sim.set_device_power("ac_bedroom", DevicePowerState.ON)
    sim.set_ac_target("ac_bedroom", 22.0)
    for _ in range(5):
        sim.tick(delta_seconds=60)
    print_telemetry(sim)

    # 3. Scenario 2: Leaving Home
    print_separator("SCENARIO 2 DEMO: Resident Leaves Home (Transition to AWAY Mode)")
    sim.trigger_scenario_leaving()
    print_telemetry(sim)

    # 4. Scenario 3: Water Leak Anomaly while Away
    print_separator("SCENARIO 3 DEMO: Abnormal Water Usage Anomaly (Plumbing Leak while AWAY)")
    sim.trigger_scenario_water_leak()
    # Advance 10 minutes to observe tank level drop
    for _ in range(10):
        sim.tick(delta_seconds=60)
    print_telemetry(sim)

    # Recent Events
    print_separator("Recent Simulation Event Log (Sample)")
    snap = sim.get_snapshot()
    for ev in snap.recent_events[-6:]:
        print(f"  [{ev.timestamp.strftime('%H:%M:%S')}] [{ev.severity}] {ev.source}: {ev.description}")

    print_separator("PHASE 1 SIMULATION DEMONSTRATION COMPLETE")


if __name__ == "__main__":
    run_demo()

