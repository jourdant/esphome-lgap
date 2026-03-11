"""Tests for sleep timer: expiry, lock interaction, external OFF, stale flags."""

from .lgap_model import MODE_OFF, MODE_COOL, LGAP_MODE


# ---------------------------------------------------------------------------
# Basic timer operation
# ---------------------------------------------------------------------------

class TestTimerExpiry:

    def test_timer_expires_turns_off(self, sim_on_timer):
        """Timer expires → AC turns OFF."""
        sim = sim_on_timer
        assert sim.esp.timer_active_ is True

        expired = sim.esp.loop_tick(now_ms=60 * 60 * 1000)
        assert expired is True
        assert sim.esp.timer_active_ is False
        assert sim.esp.mode == MODE_OFF
        assert sim.esp.write_update_pending is True

        sim.run_cycles(3)
        assert sim.ac.power_state == 0

    def test_timer_not_expired_before_time(self, sim_on_timer):
        sim = sim_on_timer
        expired = sim.esp.loop_tick(now_ms=30 * 60 * 1000)
        assert expired is False
        assert sim.esp.timer_active_ is True

    def test_timer_duration_preserved_after_expiry(self, sim_on_timer):
        """timer_duration_minutes_ stays set after expiry (auto-restart on next ON)."""
        sim = sim_on_timer
        sim.esp.loop_tick(now_ms=60 * 60 * 1000)
        assert sim.esp.timer_duration_minutes_ == 60.0


# ---------------------------------------------------------------------------
# Timer + mode lock
# ---------------------------------------------------------------------------

class TestTimerWithModeLock:

    def test_timer_off_goes_through_mode_lock(self, sim_on_timer):
        """Timer turning OFF must succeed even when mode lock is active."""
        sim = sim_on_timer
        sim.esp.lock_mode_ = True

        expired = sim.esp.loop_tick(now_ms=60 * 60 * 1000)
        assert expired is True
        assert sim.esp.mode == MODE_OFF
        assert sim.esp.write_update_pending is True

        sim.run_cycles(3)
        assert sim.ac.power_state == 0

    def test_timer_off_goes_through_power_only(self, sim_on_timer):
        """Timer OFF must also work in power-only mode."""
        sim = sim_on_timer
        sim.esp.power_only_mode_ = True

        expired = sim.esp.loop_tick(now_ms=60 * 60 * 1000)
        assert expired is True
        assert sim.esp.mode == MODE_OFF

        sim.run_cycles(3)
        assert sim.ac.power_state == 0


# ---------------------------------------------------------------------------
# External OFF cancellation
# ---------------------------------------------------------------------------

class TestTimerExternalOff:

    def test_wall_panel_off_cancels_timer(self, sim_on_timer):
        """Wall panel turns OFF → timer cancelled (not by our timer)."""
        sim = sim_on_timer

        sim.wall_panel.turn_off()
        sim.run_cycles(3)

        assert sim.esp.timer_active_ is False
        assert sim.esp.timer_turning_off_ is False

    def test_ha_off_cancels_timer(self, sim_on_timer):
        """HA OFF command cancels timer."""
        sim = sim_on_timer
        sim.ha_command(mode=MODE_OFF)

        assert sim.esp.timer_active_ is False

    def test_timer_turning_off_flag_persists_until_new_timer(self, sim_on_timer):
        """
        After timer fires, timer_turning_off_ stays True because control()
        already set power_state_=0 before AC confirms, so the 1→0 transition
        check never runs. The flag is only cleared by start_timer().
        """
        sim = sim_on_timer

        sim.esp.loop_tick(now_ms=60 * 60 * 1000)
        assert sim.esp.timer_turning_off_ is True

        sim.run_cycles(4)
        # Flag persists — only start_timer() resets it
        assert sim.esp.timer_turning_off_ is True

        # When AC turns ON and timer restarts, flag is cleared
        sim.wall_panel.turn_on(lgap_mode=0)
        sim.run_cycles(4)
        assert sim.esp.timer_turning_off_ is False


# ---------------------------------------------------------------------------
# Stale timer_turning_off_ flag
# ---------------------------------------------------------------------------

class TestStaleTimerTurningOff:

    def test_stale_flag_cleared_by_start_timer(self, sim_on):
        """
        After timer fires, timer_turning_off_ stays True until start_timer()
        resets it. Verify the full cycle: fire → persist → AC ON → start_timer
        clears flag → external OFF correctly cancels timer.
        """
        sim = sim_on
        sim.esp.timer_duration_minutes_ = 30.0
        sim.esp.start_timer(30.0, now_ms=0)

        # Fire timer
        sim.esp.loop_tick(now_ms=30 * 60 * 1000)
        assert sim.esp.timer_turning_off_ is True

        # AC confirms OFF — flag persists (see test above for why)
        sim.run_cycles(4)
        assert sim.esp.power_state_ == 0
        assert sim.esp.timer_turning_off_ is True  # persists

        # Turn ON again → auto-start timer → start_timer() clears flag
        sim.wall_panel.turn_on(lgap_mode=0)
        sim.run_cycles(4)
        assert sim.esp.timer_active_ is True
        assert sim.esp.timer_turning_off_ is False  # cleared by start_timer()

        # External OFF should cancel the new timer (flag is clean now)
        sim.wall_panel.turn_off()
        sim.run_cycles(4)
        assert sim.esp.timer_active_ is False


# ---------------------------------------------------------------------------
# Orphaned timer
# ---------------------------------------------------------------------------

class TestOrphanedTimer:

    def test_orphaned_timer_cancelled_on_confirmed_off(self, sim_on):
        """
        If AC is confirmed OFF but timer is still running, it's orphaned.
        The catch-all in on_message_received should cancel it.
        """
        sim = sim_on
        sim.esp.timer_active_ = True
        sim.esp.timer_end_time_ = 999999999

        sim.ha_command(mode=MODE_OFF)
        sim.run_cycles(3)

        assert sim.esp.timer_active_ is False


# ---------------------------------------------------------------------------
# Timer auto-start on ON
# ---------------------------------------------------------------------------

class TestTimerAutoStart:

    def test_auto_start_on_ha_on(self, sim):
        """When timer_duration is set and HA turns ON, timer auto-starts."""
        sim.esp.timer_duration_minutes_ = 45.0
        sim.ha_command(mode=MODE_COOL, temperature=24)
        assert sim.esp.timer_active_ is True

    def test_auto_start_on_wall_on(self, sim):
        """When timer_duration is set and wall panel turns ON, timer auto-starts."""
        sim.esp.timer_duration_minutes_ = 45.0
        # Initial cycle to get first_state_received_
        sim.run_cycle()
        assert sim.esp.first_state_received_
        assert sim.esp.ac_confirmed_off_ is True

        sim.wall_panel.turn_on(lgap_mode=0)
        sim.run_cycles(3)

        assert sim.esp.timer_active_ is True

    def test_no_auto_start_when_duration_zero(self, sim):
        """No timer if duration is 0."""
        sim.esp.timer_duration_minutes_ = 0
        sim.ha_command(mode=MODE_COOL)
        assert sim.esp.timer_active_ is False

    def test_timer_cancel_on_set_to_zero(self, sim_on_timer):
        """Setting timer duration to 0 cancels active timer via TimerDurationNumber.
        We model this by directly calling cancel_timer (which is what set_timer_duration_minutes(0) does)."""
        sim = sim_on_timer
        assert sim.esp.timer_active_ is True
        sim.esp.cancel_timer()
        assert sim.esp.timer_active_ is False
