# LGAP Climate Tests

Offline test suite for the `LGAPHVACClimate` state machine (`lgap_climate.cpp`). Uses a Python model that mirrors the C++ decision logic, allowing rapid iteration without compiling or deploying firmware.

## Quick Start

```bash
# From the repo root
pip install pytest
python -m pytest tests/ -v
```

## Architecture

```
tests/
├── lgap_model.py            # Python port of the C++ state machine
├── simulator.py             # AC unit, wall panel, and LGAP bus simulation
├── conftest.py              # Shared pytest fixtures
├── test_boot.py             # Device boot and initial state handling
├── test_control.py          # Home Assistant command flow
├── test_lock_enforcement.py # Temperature, mode, fan speed, and power-only locks
├── test_timer.py            # Sleep timer lifecycle
└── test_ha_wall_conflicts.py # HA vs wall panel race conditions
```

### `lgap_model.py` — State Machine Model

A faithful Python translation of the three core functions in `lgap_climate.cpp`:

| C++ method | Python method | Purpose |
|---|---|---|
| `control()` | `control()` | Process HA commands (mode, temp, fan) with lock checks |
| `handle_generate_lgap_request()` | `generate_request()` | Build a READ or WRITE request for the LGAP bus |
| `handle_on_message_received()` | `on_message_received()` | Process AC responses, enforce locks, manage cooldown |

The model tracks all internal flags (`write_update_pending`, `write_cooldown_remaining_`, `first_state_received_`, `ac_confirmed_off_`, `timer_turning_off_`, etc.) and includes a `log` list for debugging test failures.

### `simulator.py` — Bus Simulation

Three classes orchestrate a realistic LGAP polling loop:

- **`ACUnit`** — Models the physical indoor unit. Accepts WRITE payloads and returns current state on READ.
- **`WallPanel`** — Models the physical wall controller. Directly mutates `ACUnit` state (as the real hardware does between poll cycles).
- **`Simulation`** — Ties everything together. Each `run_cycle()` call executes one poll: ESP generates request → AC processes → ESP receives response.

Key helper methods on `Simulation`:

- `run_cycles(n)` — Run multiple poll cycles
- `ha_command(mode=..., temperature=..., fan_mode=...)` — Simulate a Home Assistant service call
- `ha_turn_on()` / `ha_turn_off()` — Convenience wrappers

### `conftest.py` — Fixtures

| Fixture | State |
|---|---|
| `sim` | Fresh simulation, AC off, no locks |
| `sim_on` | AC on (cool, 24°C, auto fan), `first_state_received_` set |
| `sim_on_locked_temp` | AC on with temperature lock at 24°C |
| `sim_on_locked_mode` | AC on with mode lock in cool mode |
| `sim_on_timer` | AC on with a 60-minute sleep timer running |

## Test Modules

### `test_boot.py` — Boot Sequence (6 tests)

Covers the critical first-message-after-reboot scenarios:

- `first_state_received_` flag is set on first AC message
- No false "wall panel turned ON" detection on boot (checks `ac_confirmed_off_`)
- Lock enforcement is skipped on the very first AC message
- Deferred timer starts when AC confirms ON, skips when OFF
- `ac_confirmed_off_` tracking and cooldown interaction

### `test_control.py` — HA Command Flow (10 tests)

Validates that `control()` correctly processes Home Assistant service calls:

- Turn off (basic, with all locks active, repeated)
- Mode changes (cool→heat, blocked by mode lock)
- Temperature changes (basic, clamped to 16–30 range, blocked by lock)
- Fan speed changes (basic, blocked by lock)

### `test_lock_enforcement.py` — Lock Enforcement (16 tests)

The largest module, covering all four lock types:

- **Temperature lock**: wall change reverted, HA blocked, no useless writes when AC off, locked value survives OFF→ON cycle
- **Mode lock**: wall mode reverted, OFF always allowed, HA mode blocked, ON-from-OFF allowed
- **Fan speed lock**: wall fan reverted, HA blocked, no writes when AC off
- **Power-only mode**: only OFF allowed, temp/fan/mode blocked from both HA and wall panel
- **`write_was_pending` fix**: verifies the corrective WRITE is actually generated after lock violation (the core bug fix), and that lock detection works after unrelated write cooldown

### `test_timer.py` — Sleep Timer (13 tests)

Covers the full timer lifecycle:

- Basic expiry turns AC off, not-yet-expired stays active, duration preserved after expiry
- Timer OFF goes through mode lock and power-only mode
- External OFF cancels timer (wall panel and HA)
- `timer_turning_off_` flag lifecycle (persists until `start_timer()` clears it)
- Orphaned timer cancelled on confirmed OFF
- Auto-start on HA turn-on, wall panel turn-on, and no start when duration is zero

### `test_ha_wall_conflicts.py` — Race Conditions (9 tests)

Models real-world conflicts between Home Assistant commands and wall panel changes:

- HA OFF overrides pending lock WRITE
- HA OFF during lock enforcement cooldown
- Wall panel fights lock repeatedly (convergence test)
- Simultaneous HA temp change + wall mode change
- Wall turns ON right after HA OFF (HA intent wins)
- Wall turns ON during OFF cooldown (accepted after cooldown)
- Timer expiry + HA OFF at the same time
- Wall ON after timer OFF restarts timer
- Combined temp + mode lock with wall changing both

## How the Simulation Works

A single poll cycle (`sim.run_cycle()`) models what happens every ~1 second on the real LGAP bus:

```
1. ESP calls generate_request()
   → Returns READ (normal poll) or WRITE (pending command)

2. AC unit processes the request
   → On WRITE: updates its internal state
   → Returns current state in all cases

3. ESP calls on_message_received() with AC's response
   → Updates HA-visible state
   → Detects lock violations → sets write_update_pending
   → Manages write cooldown (2 cycles after each WRITE)
```

Wall panel changes happen *between* cycles by directly mutating the AC unit's state, matching how the real hardware works (the wall controller talks directly to the indoor unit, not through the LGAP bus).

## Adding New Tests

1. Pick the right module (or create a new `test_*.py` file)
2. Use an existing fixture from `conftest.py` or create a new one
3. Set up preconditions (locks, timer, wall panel state)
4. Run cycles and assert on both `sim.esp.*` (ESP internal state) and `sim.ac.*` (physical AC state)

Example:

```python
def test_example(sim_on_locked_temp):
    sim = sim_on_locked_temp

    # Wall panel changes temperature
    sim.wall_panel.set_temperature(20)

    # Run enough cycles for detection + WRITE + cooldown + confirmation
    sim.run_cycles(5)

    # Verify lock enforcement reverted the change
    assert sim.ac.target_temperature == 24.0
    assert sim.esp.target_temperature_ == 24.0
```

## Keeping the Model in Sync

The Python model must stay aligned with `lgap_climate.cpp`. When modifying the C++ code:

1. Update the corresponding method in `lgap_model.py`
2. Run `python -m pytest tests/ -v` to verify all tests still pass
3. Add new tests for any new behavior
