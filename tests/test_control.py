"""Tests for HA command flow through control()."""

from .lgap_model import MODE_OFF, MODE_COOL, MODE_HEAT, MODE_DRY, FAN_LOW, FAN_HIGH


class TestTurnOff:
    def test_off_command_reaches_ac(self, sim_on):
        """Basic OFF from HA should turn off the AC."""
        s = sim_on
        s.ha_turn_off()
        assert s.esp.write_update_pending is True
        assert s.esp.power_state_ == 0

        s.run_cycles(4)
        assert s.ac.power_state == 0
        assert s.esp.mode == MODE_OFF

    def test_off_with_all_locks_active(self, sim_on):
        """OFF should go through even when all locks are active."""
        s = sim_on
        s.esp.lock_temperature_ = True
        s.esp.lock_fan_speed_ = True
        s.esp.lock_mode_ = True

        s.ha_turn_off()
        assert s.esp.write_update_pending is True
        s.run_cycles(4)
        assert s.ac.power_state == 0

    def test_repeated_off_still_sends_write(self, sim_on):
        """Sending OFF when already OFF should still send a WRITE."""
        s = sim_on
        s.ha_turn_off()
        s.run_cycles(4)
        assert s.esp.mode == MODE_OFF

        # Send OFF again
        s.ha_command(mode=MODE_OFF)
        assert s.esp.write_update_pending is True


class TestModeChange:
    def test_cool_to_heat(self, sim_on):
        """Basic mode change from COOL to HEAT."""
        s = sim_on
        s.ha_command(mode=MODE_HEAT)
        assert s.esp.write_update_pending is True
        assert s.esp.mode_ == 4  # HEAT LGAP value

        s.run_cycles(4)
        assert s.ac.mode == 4

    def test_mode_change_blocked_by_mode_lock(self, sim_on_locked_mode):
        """Mode lock blocks COOL→HEAT from HA."""
        s = sim_on_locked_mode
        s.ha_command(mode=MODE_HEAT)
        # Should be blocked, no write pending
        assert s.esp.mode == MODE_COOL


class TestTemperatureChange:
    def test_set_temperature(self, sim_on):
        """Basic temperature change from HA."""
        s = sim_on
        s.ha_command(temperature=22.0)
        assert s.esp.target_temperature_ == 22.0
        assert s.esp.write_update_pending is True

        s.run_cycles(4)
        assert s.ac.target_temperature == 22.0

    def test_temp_clamped_to_range(self, sim_on):
        """Temperature should be clamped to 16-30 range."""
        s = sim_on
        s.ha_command(temperature=10.0)
        assert s.esp.target_temperature_ == 16.0

        s.ha_command(temperature=40.0)
        assert s.esp.target_temperature_ == 30.0

    def test_temp_blocked_by_lock(self, sim_on_locked_temp):
        """Temperature lock blocks temp changes from HA."""
        s = sim_on_locked_temp
        s.ha_command(temperature=20.0)
        assert s.esp.target_temperature_ == 24.0  # unchanged


class TestFanSpeed:
    def test_set_fan_speed(self, sim_on):
        """Basic fan speed change from HA."""
        s = sim_on
        s.ha_command(fan_mode=FAN_LOW)
        assert s.esp.fan_speed_ == 1
        assert s.esp.write_update_pending is True

        s.run_cycles(4)
        assert s.ac.fan_speed == 1

    def test_fan_blocked_by_lock(self, sim_on):
        """Fan speed lock blocks fan changes from HA."""
        s = sim_on
        s.esp.lock_fan_speed_ = True
        s.ha_command(fan_mode=FAN_LOW)
        assert s.esp.fan_speed_ == 4  # unchanged (AUTO)
