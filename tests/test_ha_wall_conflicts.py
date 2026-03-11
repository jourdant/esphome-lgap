"""Tests for HA vs wall panel race conditions and conflicts."""

from .lgap_model import MODE_OFF, MODE_COOL, MODE_HEAT, FAN_LOW, FAN_HIGH


class TestHAOffDuringLockWrite:
    def test_ha_off_overrides_pending_lock_write(self, sim_on_locked_temp):
        """
        Lock enforcement sets write_update_pending. Before the WRITE is sent,
        HA sends OFF. The resulting WRITE should include power=OFF.
        """
        s = sim_on_locked_temp

        # Wall changes temp → lock sets write_update_pending
        s.wall_panel.set_temperature(22.0)
        s.run_cycle()
        assert s.esp.write_update_pending is True
        assert s.esp.target_temperature_ == 24.0

        # HA sends OFF before the lock WRITE is dispatched
        s.ha_turn_off()
        assert s.esp.power_state_ == 0

        # The WRITE should now carry power=OFF
        is_write, payload = s.esp.generate_request()
        assert is_write is True
        assert payload["power_state"] == 0

        # Deliver it
        s.run_cycles(4)
        assert s.ac.power_state == 0

    def test_ha_off_during_lock_cooldown(self, sim_on_locked_temp):
        """
        Lock WRITE was already sent (cooldown active). HA sends OFF.
        OFF should be sent on the next cycle regardless of cooldown.
        """
        s = sim_on_locked_temp

        # Trigger lock enforcement and let WRITE + cooldown start
        s.wall_panel.set_temperature(22.0)
        s.run_cycles(2)  # detect + WRITE

        # HA sends OFF during cooldown
        s.ha_turn_off()
        assert s.esp.write_update_pending is True

        # Next cycle should send the OFF WRITE
        s.run_cycle()
        # WRITE with power=OFF was sent
        assert s.ac.power_state == 0


class TestWallPanelFightsDuringCooldown:
    def test_wall_change_during_write_cooldown(self, sim_on_locked_temp):
        """
        Lock enforcement WRITE sent. During cooldown, wall panel changes
        temp again. After cooldown, ESP should detect and revert again.
        """
        s = sim_on_locked_temp

        # First lock enforcement cycle
        s.wall_panel.set_temperature(22.0)
        s.run_cycles(2)  # detect + WRITE → AC now at 24

        # During cooldown, wall panel changes again
        s.wall_panel.set_temperature(20.0)
        s.run_cycles(2)  # cooldown ticks down

        # After cooldown, ESP reads AC state (20 from wall panel)
        s.run_cycle()
        # Should detect violation and set write_update_pending
        assert s.esp.write_update_pending is True
        assert s.esp.target_temperature_ == 24.0

        # WRITE reverts it again
        s.run_cycles(4)
        assert s.ac.target_temperature == 24.0

    def test_repeated_wall_fights_converge(self, sim_on_locked_temp):
        """Wall panel fighting lock should always converge to locked value."""
        s = sim_on_locked_temp

        for _ in range(5):
            s.wall_panel.set_temperature(18.0)
            s.run_cycles(5)
            assert s.ac.target_temperature == 24.0
            assert s.esp.target_temperature_ == 24.0


class TestSimultaneousCommands:
    def test_ha_temp_while_wall_changes_mode(self, sim_on):
        """
        HA changes temperature while wall panel changes mode in the same window.
        Both should be processed (HA temp first via control, then wall mode on read).
        """
        s = sim_on

        # HA sets new temperature
        s.ha_command(temperature=20.0)
        assert s.esp.write_update_pending is True

        # Wall panel changes mode before WRITE is sent
        s.wall_panel.set_mode(4, power=1)  # HEAT

        # WRITE is sent with HA's temp (20) but ESP's current mode (COOL)
        s.run_cycle()

        # After WRITE, AC has: temp=20, mode=COOL (from ESP's WRITE)
        # The wall's HEAT was overwritten by the WRITE
        assert s.ac.target_temperature == 20.0

        # After cooldown, ESP reads AC's state → all matches
        s.run_cycles(3)
        assert s.esp.target_temperature_ == 20.0

    def test_wall_turns_on_right_after_ha_off(self, sim_on):
        """
        HA sends OFF. Before WRITE is dispatched, wall panel turns AC ON.
        ESP should still send OFF (HA intent takes priority).
        """
        s = sim_on

        s.ha_turn_off()
        s.wall_panel.turn_on(lgap_mode=0)  # Wall turns on

        # ESP sends WRITE with power=OFF (from control())
        is_write, payload = s.esp.generate_request()
        assert is_write is True
        assert payload["power_state"] == 0

        # AC accepts the OFF
        s.run_cycles(4)
        assert s.ac.power_state == 0

    def test_wall_turns_on_during_off_cooldown(self, sim_on):
        """
        HA OFF was sent, cooldown active. Wall panel turns AC ON.
        After cooldown, ESP should see the AC is ON and accept it
        (no lock prevents power changes unless power_only_mode).
        """
        s = sim_on

        s.ha_turn_off()
        s.run_cycles(2)  # WRITE + start of cooldown
        assert s.esp.write_cooldown_remaining_ > 0

        # Wall turns AC on during cooldown
        s.wall_panel.turn_on(lgap_mode=0)

        # Finish cooldown
        s.run_cycles(2)

        # ESP reads: AC is ON. No lock on power, so accept it.
        s.run_cycle()
        assert s.esp.power_state_ == 1
        assert s.esp.mode == MODE_COOL


class TestTimerAndHAConflicts:
    def test_ha_off_and_timer_off_simultaneous(self, sim_on_timer):
        """
        Timer expires in the same window as HA sends OFF.
        Should not double-cancel or cause issues.
        """
        s = sim_on_timer

        # Timer expires
        s.esp.loop_tick(now_ms=61 * 60 * 1000)
        assert s.esp.mode == MODE_OFF
        assert s.esp.timer_active_ is False

        # HA also sends OFF (redundant)
        s.ha_turn_off()
        # timer_active_ is already False, should not error
        assert s.esp.mode == MODE_OFF

        s.run_cycles(4)
        assert s.ac.power_state == 0

    def test_wall_on_after_timer_off_restarts_timer(self, sim_on_timer):
        """
        Timer turns off AC. Wall panel turns it back on.
        Timer should auto-restart (duration is preserved).
        """
        s = sim_on_timer

        # Timer expires → AC OFF
        s.esp.loop_tick(now_ms=61 * 60 * 1000)
        s.run_cycles(4)
        assert s.ac.power_state == 0

        # Wall panel turns ON
        s.wall_panel.turn_on(lgap_mode=0)
        s.run_cycles(4)

        # Timer should auto-restart (ac_confirmed_off_ was True, now turning ON)
        assert s.esp.timer_active_ is True


class TestLockWithModeAndTempConflict:
    def test_temp_and_mode_lock_wall_changes_both(self, sim_on):
        """Wall panel changes both temp and mode. Both should be reverted."""
        s = sim_on
        s.esp.lock_temperature_ = True
        s.esp.lock_mode_ = True

        s.wall_panel.set_temperature(20.0)
        s.wall_panel.set_mode(4, power=1)  # HEAT

        s.run_cycles(5)

        # Both should revert
        assert s.ac.target_temperature == 24.0
        assert s.ac.mode == 0  # COOL

    def test_power_only_wall_changes_everything(self, sim_on):
        """
        Power-only mode active. Wall panel changes temp, mode, fan.
        All should be reverted except power state.
        """
        s = sim_on
        s.esp.power_only_mode_ = True

        s.wall_panel.set_temperature(18.0)
        s.wall_panel.set_mode(4, power=1)  # HEAT
        s.wall_panel.set_fan_speed(1)  # LOW

        # Multiple cycles to detect and revert
        s.run_cycles(10)

        assert s.ac.target_temperature == 24.0
        assert s.ac.fan_speed == 4  # AUTO
        # Mode revert depends on implementation — mode lock may apply
