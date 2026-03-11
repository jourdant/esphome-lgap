"""Tests for boot sequence: first state, deferred timer, ac_confirmed_off."""

from .lgap_model import MODE_OFF, MODE_COOL


class TestFirstState:
    def test_first_state_received_flag(self, sim):
        """first_state_received_ should be set after first AC message."""
        s = sim
        assert s.esp.first_state_received_ is False

        s.ac.power_state = 1
        s.ac.mode = 0
        s.run_cycle()
        assert s.esp.first_state_received_ is True

    def test_no_false_wall_panel_detection_on_boot(self, sim):
        """
        On boot, if HA restored OFF but AC is actually ON,
        don't falsely detect 'wall panel turned ON'.
        ac_confirmed_off_ should be False before first state.
        """
        s = sim
        assert s.esp.ac_confirmed_off_ is False

        # HA restored state is OFF, but AC is actually ON
        s.esp.power_state_ = 0
        s.esp.mode = MODE_OFF
        s.ac.power_state = 1
        s.ac.mode = 0

        # First message: should NOT trigger wall panel detection
        # because ac_confirmed_off_ is False (not confirmed by AC)
        s.run_cycle()
        assert s.esp.power_state_ == 1
        assert s.esp.mode == MODE_COOL
        # Timer should NOT have started (no wall panel detection)
        assert s.esp.timer_active_ is False

    def test_lock_not_enforced_on_first_message(self, sim):
        """Lock enforcement should be skipped on the very first AC message."""
        s = sim
        s.esp.lock_temperature_ = True
        s.esp.target_temperature_ = 24.0

        s.ac.power_state = 1
        s.ac.target_temperature = 20.0

        s.run_cycle()
        # Should accept AC's value, not enforce lock
        assert s.esp.target_temperature_ == 20.0


class TestDeferredTimer:
    def test_deferred_timer_starts_when_ac_on(self, sim):
        """If timer was configured before boot, start it when AC confirms ON."""
        s = sim
        s.esp.timer_pending_on_boot_ = True
        s.esp.timer_duration_minutes_ = 120.0

        s.ac.power_state = 1
        s.ac.mode = 0
        s.run_cycle()

        assert s.esp.timer_pending_on_boot_ is False
        assert s.esp.timer_active_ is True

    def test_deferred_timer_skipped_when_ac_off(self, sim):
        """If timer was configured but AC is OFF on boot, skip timer start."""
        s = sim
        s.esp.timer_pending_on_boot_ = True
        s.esp.timer_duration_minutes_ = 120.0

        s.ac.power_state = 0
        s.run_cycle()

        assert s.esp.timer_pending_on_boot_ is False
        assert s.esp.timer_active_ is False

    def test_deferred_timer_cleared_on_confirmed_off(self, sim):
        """Deferred boot timer cleared if AC confirms OFF."""
        s = sim
        s.esp.timer_pending_on_boot_ = True

        s.ac.power_state = 0
        s.run_cycle()
        assert s.esp.timer_pending_on_boot_ is False


class TestAcConfirmedOff:
    def test_tracks_ac_power_state(self, sim):
        """ac_confirmed_off_ reflects the AC's actual reported power state."""
        s = sim
        s.ac.power_state = 1
        s.run_cycle()
        assert s.esp.ac_confirmed_off_ is False

        s.ac.power_state = 0
        # Need to make sure we're past cooldown if any
        s.esp.write_update_pending = False
        s.esp.write_cooldown_remaining_ = 0
        s.run_cycle()
        assert s.esp.ac_confirmed_off_ is True

    def test_not_updated_during_cooldown(self, sim_on):
        """ac_confirmed_off_ should NOT update during write cooldown."""
        s = sim_on
        # Trigger a write + cooldown
        s.ha_command(temperature=22.0)
        s.run_cycle()  # WRITE sent → cooldown starts

        # During cooldown, AC reports OFF but we should ignore it
        s.ac.power_state = 0
        old_confirmed = s.esp.ac_confirmed_off_
        s.run_cycle()  # cooldown cycle
        assert s.esp.ac_confirmed_off_ == old_confirmed  # unchanged during cooldown
