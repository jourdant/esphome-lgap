"""Tests for lock enforcement: temperature, mode, fan speed, power-only, write_was_pending."""

from .lgap_model import (
    MODE_OFF, MODE_COOL, MODE_HEAT, MODE_DRY, MODE_FAN_ONLY,
    FAN_LOW, FAN_HIGH, FAN_AUTO,
    LGAP_MODE,
)


# ---------------------------------------------------------------------------
# Temperature lock
# ---------------------------------------------------------------------------

class TestTemperatureLock:

    def test_wall_change_reverted(self, sim_on_locked_temp):
        """Wall panel changes temp → ESP sends WRITE to revert it."""
        sim = sim_on_locked_temp
        assert sim.esp.target_temperature_ == 24.0

        sim.wall_panel.set_temperature(22)
        sim.run_cycles(5)

        assert sim.ac.target_temperature == 24.0
        assert sim.esp.target_temperature_ == 24.0

    def test_ha_change_blocked(self, sim_on_locked_temp):
        """HA temp change is blocked when lock active."""
        sim = sim_on_locked_temp
        sim.ha_command(temperature=20)
        assert sim.esp.target_temperature_ == 24.0
        assert sim.esp.write_update_pending is False

    def test_lock_while_off_no_writes(self, sim_on_locked_temp):
        """When AC is OFF, temp difference does NOT trigger useless writes."""
        sim = sim_on_locked_temp
        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)

        sim.wall_panel.set_temperature(20)
        # Capture pending state before cycles
        sim.run_cycles(3)

        assert sim.esp.write_update_pending is False
        assert sim.esp.target_temperature_ == 24.0

    def test_locked_value_preserved_after_off(self, sim_on_locked_temp):
        """Locked temp is preserved even after AC goes OFF and back ON."""
        sim = sim_on_locked_temp
        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)

        sim.wall_panel.set_temperature(18)
        sim.run_cycles(2)

        sim.ha_command(mode=MODE_COOL)
        sim.run_cycles(5)

        assert sim.esp.target_temperature_ == 24.0
        assert sim.ac.target_temperature == 24.0


# ---------------------------------------------------------------------------
# Mode lock
# ---------------------------------------------------------------------------

class TestModeLock:

    def test_wall_mode_change_reverted(self, sim_on_locked_mode):
        """Wall panel changes COOL→HEAT → ESP reverts."""
        sim = sim_on_locked_mode
        assert sim.esp.mode == MODE_COOL

        sim.wall_panel.set_mode(LGAP_MODE[MODE_HEAT])
        sim.run_cycles(5)

        assert sim.ac.mode == LGAP_MODE[MODE_COOL]
        assert sim.esp.mode == MODE_COOL

    def test_mode_lock_allows_off(self, sim_on_locked_mode):
        """Mode lock must NOT block turning OFF (bug fix)."""
        sim = sim_on_locked_mode

        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)

        assert sim.esp.mode == MODE_OFF
        assert sim.esp.power_state_ == 0
        assert sim.ac.power_state == 0

    def test_ha_mode_change_blocked(self, sim_on_locked_mode):
        """HA mode change (COOL→HEAT) is blocked by mode lock."""
        sim = sim_on_locked_mode
        sim.ha_command(mode=MODE_HEAT)
        assert sim.esp.mode == MODE_COOL

    def test_ha_mode_from_off_allowed(self, sim_on_locked_mode):
        """Mode lock allows turning ON from OFF (lock only blocks mode-to-mode changes)."""
        sim = sim_on_locked_mode
        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)
        assert sim.esp.mode == MODE_OFF

        sim.ha_command(mode=MODE_COOL)
        sim.run_cycles(3)
        assert sim.esp.mode == MODE_COOL


# ---------------------------------------------------------------------------
# Fan speed lock
# ---------------------------------------------------------------------------

class TestFanSpeedLock:

    def test_wall_fan_change_reverted(self, sim_on):
        """Wall panel changes fan → ESP reverts when lock active."""
        sim = sim_on
        sim.esp.lock_fan_speed_ = True
        assert sim.esp.fan_speed_ == 4  # AUTO

        sim.wall_panel.set_fan_speed(1)  # LOW
        sim.run_cycles(5)

        assert sim.ac.fan_speed == 4  # reverted to AUTO
        assert sim.esp.fan_speed_ == 4

    def test_ha_fan_change_blocked(self, sim_on):
        sim = sim_on
        sim.esp.lock_fan_speed_ = True
        sim.ha_command(fan_mode=FAN_LOW)
        assert sim.esp.fan_speed_ == 4  # unchanged

    def test_fan_lock_while_off_no_writes(self, sim_on):
        """Fan diff while AC OFF should not trigger writes."""
        sim = sim_on
        sim.esp.lock_fan_speed_ = True
        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)

        sim.wall_panel.set_fan_speed(1)  # LOW
        sim.run_cycles(3)

        assert sim.esp.write_update_pending is False
        assert sim.esp.fan_speed_ == 4  # preserved


# ---------------------------------------------------------------------------
# Power-only mode
# ---------------------------------------------------------------------------

class TestPowerOnlyMode:

    def test_only_off_allowed(self, sim_on):
        """Power-only mode blocks mode changes except OFF."""
        sim = sim_on
        sim.esp.power_only_mode_ = True

        sim.ha_command(mode=MODE_HEAT)
        assert sim.esp.mode == MODE_COOL  # unchanged

        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)
        assert sim.esp.mode == MODE_OFF

    def test_temp_blocked(self, sim_on):
        sim = sim_on
        sim.esp.power_only_mode_ = True
        sim.ha_command(temperature=20)
        assert sim.esp.target_temperature_ == 24.0

    def test_fan_blocked(self, sim_on):
        sim = sim_on
        sim.esp.power_only_mode_ = True
        sim.ha_command(fan_mode=FAN_LOW)
        assert sim.esp.fan_speed_ == 4

    def test_wall_temp_reverted(self, sim_on):
        """Wall panel temp change reverted in power-only mode."""
        sim = sim_on
        sim.esp.power_only_mode_ = True

        sim.wall_panel.set_temperature(20)
        sim.run_cycles(5)

        assert sim.ac.target_temperature == 24.0

    def test_wall_mode_reverted(self, sim_on):
        """Wall panel mode change reverted in power-only mode."""
        sim = sim_on
        sim.esp.power_only_mode_ = True

        sim.wall_panel.set_mode(LGAP_MODE[MODE_HEAT])
        sim.run_cycles(5)

        assert sim.ac.mode == LGAP_MODE[MODE_COOL]


# ---------------------------------------------------------------------------
# write_was_pending fix
# ---------------------------------------------------------------------------

class TestWriteWasPending:

    def test_write_generated_after_lock_violation(self, sim_on_locked_temp):
        """
        After a lock violation sets write_update_pending during on_message_received,
        the NEXT generate_request() must produce a WRITE (not a READ).
        This is the write_was_pending bug: if we cleared write_update_pending at the
        end of on_message_received instead of using write_was_pending snapshot, the
        revert WRITE would never be sent.
        """
        sim = sim_on_locked_temp

        sim.wall_panel.set_temperature(20)
        sim.run_cycle()

        # After this cycle, ESP saw the wall change and set write_update_pending
        assert sim.esp.write_update_pending is True

        is_write, payload = sim.esp.generate_request()
        assert is_write is True
        assert payload["target_temperature"] == 24.0

    def test_lock_detects_after_unrelated_write_cooldown(self, sim_on_locked_temp):
        """
        An unrelated WRITE is sent (e.g. HA changed temp while unlocked).
        During that WRITE's response, the state block is skipped (write_update_pending
        was True), so the lock can't detect the wall change yet. After cooldown
        expires, the next READ picks up the wall change and the lock reverts it.
        """
        sim = sim_on_locked_temp

        # Unlock briefly to send a write, then re-lock
        sim.esp.lock_temperature_ = False
        sim.ha_command(temperature=25)
        sim.esp.lock_temperature_ = True
        assert sim.esp.write_update_pending is True

        # Wall changes temp while the write is in flight
        sim.wall_panel.set_temperature(20)
        sim.run_cycle()  # WRITE (temp=25) sent → AC accepts → wall's 20 was overridden

        # WRITE response processed → cooldown starts. State block was skipped.
        assert sim.esp.write_cooldown_remaining_ == 2

        # Wall changes temp again during cooldown
        sim.wall_panel.set_temperature(20)
        sim.run_cycles(2)  # cooldown ticks down

        # After cooldown: next READ detects wall's 20 → lock enforcement triggers
        sim.run_cycle()
        assert sim.esp.write_update_pending is True
        assert sim.esp.target_temperature_ == 25.0  # locked value preserved

        # WRITE reverts AC back to 25
        sim.run_cycles(4)
        assert sim.ac.target_temperature == 25.0
