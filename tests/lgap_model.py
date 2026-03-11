"""
Python model of the LGAPHVACClimate state machine.

Faithfully mirrors the decision logic in lgap_climate.cpp for offline testing.
Only models state transitions and flag logic — not UART/protocol bytes.
"""

# Climate modes (matching ESPHome enum values)
MODE_OFF = "OFF"
MODE_COOL = "COOL"
MODE_DRY = "DRY"
MODE_FAN_ONLY = "FAN_ONLY"
MODE_HEAT_COOL = "HEAT_COOL"
MODE_HEAT = "HEAT"

# Internal LGAP mode values
LGAP_MODE = {
    MODE_COOL: 0,
    MODE_DRY: 1,
    MODE_FAN_ONLY: 2,
    MODE_HEAT_COOL: 3,
    MODE_HEAT: 4,
}

LGAP_MODE_REVERSE = {v: k for k, v in LGAP_MODE.items()}

# Fan modes
FAN_LOW = "LOW"
FAN_MEDIUM = "MEDIUM"
FAN_HIGH = "HIGH"
FAN_AUTO = "AUTO"
FAN_QUIET = "QUIET"
FAN_FOCUS = "FOCUS"

LGAP_FAN = {
    FAN_LOW: 1,
    FAN_MEDIUM: 2,
    FAN_HIGH: 3,
    FAN_AUTO: 4,
    FAN_QUIET: 5,
    FAN_FOCUS: 6,
}

LGAP_FAN_REVERSE = {v: k for k, v in LGAP_FAN.items()}


class LGAPClimateModel:
    """Models the state machine of LGAPHVACClimate (lgap_climate.cpp)."""

    def __init__(self):
        # Public state (what HA sees)
        self.mode = MODE_OFF
        self.target_temperature = 24.0
        self.fan_mode = FAN_AUTO

        # Internal LGAP state
        self.power_state_ = 0
        self.mode_ = 0
        self.fan_speed_ = 4  # AUTO
        self.target_temperature_ = 24.0

        # Write control
        self.write_update_pending = False
        self.write_cooldown_remaining_ = 0

        # Locks
        self.lock_temperature_ = False
        self.lock_fan_speed_ = False
        self.lock_mode_ = False
        self.power_only_mode_ = False

        # State tracking
        self.first_state_received_ = False
        self.ac_confirmed_off_ = False

        # Timer state
        self.timer_active_ = False
        self.timer_pending_on_boot_ = False
        self.timer_turning_off_ = False
        self.timer_duration_minutes_ = 0.0
        self.timer_end_time_ = 0

        # Log for debugging tests
        self.log = []

    def _log(self, level, msg):
        self.log.append(f"[{level}] {msg}")

    # -- control() mirrors lgap_climate.cpp lines 422-661 --

    def control(self, mode=None, temperature=None, fan_mode=None):
        """Process a command from Home Assistant."""

        if self.power_only_mode_:
            if mode is not None:
                if mode == MODE_OFF:
                    if self.mode != mode:
                        self.power_state_ = 0
                        self.write_update_pending = True
                        self.mode = mode
                else:
                    self._log("W", "Mode change blocked - power-only mode is active")
            if temperature is not None or fan_mode is not None:
                self._log("W", "Control changes blocked - power-only mode")
            return

        if mode is not None:
            # Mode lock check — allows OFF through (fixed bug)
            requested_mode = mode
            if self.lock_mode_ and self.mode != MODE_OFF and requested_mode != MODE_OFF:
                self._log("W", "Mode change blocked - mode lock is active")
                return

            if self.mode != mode:
                if mode == MODE_OFF:
                    self.power_state_ = 0
                elif mode in LGAP_MODE:
                    self.power_state_ = 1
                    self.mode_ = LGAP_MODE[mode]

                # Timer auto-start on ON
                was_off = (self.mode == MODE_OFF)
                turning_on = (mode != MODE_OFF)
                if was_off and turning_on and self.timer_duration_minutes_ > 0:
                    self._log("I", f"AC turning ON - auto-starting sleep timer for {self.timer_duration_minutes_:.0f} minutes")
                    self.start_timer(self.timer_duration_minutes_)

                # Cancel timer on OFF
                if mode == MODE_OFF and self.timer_active_:
                    self._log("I", "AC turned OFF via HA, cancelling sleep timer")
                    self.cancel_timer()

            self.write_update_pending = True
            self.mode = mode

        if fan_mode is not None:
            if self.lock_fan_speed_:
                self._log("W", "Fan speed change blocked - fan speed lock is active")
                return
            if self.fan_mode != fan_mode and fan_mode in LGAP_FAN:
                self.fan_speed_ = LGAP_FAN[fan_mode]
                self.write_update_pending = True
                self.fan_mode = fan_mode

        if temperature is not None:
            if self.lock_temperature_:
                self._log("W", "Temperature change blocked - temperature lock is active")
                return
            temp = max(16.0, min(30.0, temperature))
            self.target_temperature_ = temp
            self.target_temperature = temp
            self.write_update_pending = True

    # -- generate_request() mirrors handle_generate_lgap_request() lines 663-692 --

    def generate_request(self):
        """Generate a READ or WRITE request. Returns (is_write, payload_dict)."""
        is_write = self.write_update_pending
        payload = {
            "power_state": self.power_state_,
            "is_write": is_write,
            "mode": self.mode_,
            "fan_speed": self.fan_speed_,
            "target_temperature": self.target_temperature_,
        }
        return is_write, payload

    # -- on_message_received() mirrors handle_on_message_received() lines 694-1161 --

    def on_message_received(self, power_state, mode, fan_speed, target_temperature):
        """
        Process a response from the AC unit.
        Arguments are the decoded values from the AC's response message.
        Returns True if state was published to HA.
        """
        publish_update = False
        write_was_pending = self.write_update_pending

        if not self.write_update_pending and self.write_cooldown_remaining_ == 0:
            # -- Mode / power state --
            if power_state != self.power_state_ or mode != self.mode_:
                ha_mode = LGAP_MODE_REVERSE.get(mode, MODE_OFF)
                if power_state == 0:
                    ha_mode = MODE_OFF

                # Mode lock enforcement
                if (self.first_state_received_
                        and (self.lock_mode_ or self.power_only_mode_)
                        and mode != self.mode_
                        and self.power_state_ == 1):
                    self._log("W", "Mode changed at wall controller while lock active - reverting")
                    self.write_update_pending = True
                else:
                    was_off = (self.power_state_ == 0)
                    turning_on = (power_state == 1)

                    publish_update = True
                    self.mode_ = mode
                    self.power_state_ = power_state
                    self.mode = ha_mode

                    if not self.first_state_received_ and self.timer_pending_on_boot_:
                        self.timer_pending_on_boot_ = False
                        if power_state == 1:
                            self._log("I", "First AC state confirms unit is ON, starting deferred timer")
                            self.start_timer(self.timer_duration_minutes_)
                        else:
                            self._log("I", "First AC state shows unit is OFF, skipping deferred timer")
                    elif self.first_state_received_ and self.ac_confirmed_off_ and turning_on and self.timer_duration_minutes_ > 0:
                        self._log("I", "AC turned ON from wall panel, starting sleep timer")
                        self.start_timer(self.timer_duration_minutes_)

                    # Cancel timer on external OFF
                    if not was_off and power_state == 0 and self.timer_active_:
                        if self.timer_turning_off_:
                            self.timer_turning_off_ = False
                        else:
                            self._log("I", "AC turned OFF externally while timer active, cancelling timer")
                            self.cancel_timer()

            # Track AC-confirmed power state
            self.ac_confirmed_off_ = (power_state == 0)

            # Cancel orphaned timer
            if power_state == 0 and self.timer_active_:
                self._log("I", "AC confirmed OFF, cancelling orphaned sleep timer")
                self.cancel_timer()

            # Clear deferred boot timer
            if power_state == 0 and self.timer_pending_on_boot_:
                self._log("I", "AC confirmed OFF on boot, clearing deferred timer")
                self.timer_pending_on_boot_ = False

            # -- Fan speed --
            if fan_speed != self.fan_speed_ and fan_speed != 0:
                if self.first_state_received_ and (self.lock_fan_speed_ or self.power_only_mode_) and fan_speed != self.fan_speed_:
                    if self.power_state_ == 1:
                        self._log("W", "Fan speed changed at wall controller while lock active - reverting")
                        self.write_update_pending = True
                else:
                    self.fan_speed_ = fan_speed
                    if fan_speed in LGAP_FAN_REVERSE:
                        self.fan_mode = LGAP_FAN_REVERSE[fan_speed]
                    publish_update = True

            # -- Target temperature --
            if target_temperature != self.target_temperature_:
                if self.first_state_received_ and (self.lock_temperature_ or self.power_only_mode_):
                    if self.power_state_ == 1:
                        self._log("W", f"Temperature changed at wall controller ({self.target_temperature_}→{target_temperature}) while lock active - reverting")
                        self.write_update_pending = True
                else:
                    self.target_temperature_ = target_temperature
                    self.target_temperature = target_temperature
                    publish_update = True

        # Cooldown management (uses write_was_pending, not current flag)
        if write_was_pending:
            self._log("V", "Write response processed, starting cooldown (2 cycles)")
            self.write_update_pending = False
            self.write_cooldown_remaining_ = 2
        elif self.write_cooldown_remaining_ > 0:
            self.write_cooldown_remaining_ -= 1
            self._log("V", f"Write cooldown: {self.write_cooldown_remaining_} cycles remaining")

        if not self.first_state_received_:
            self.first_state_received_ = True
            self._log("D", "First state received from AC, lock enforcement now active")

        return publish_update

    # -- Timer methods --

    def start_timer(self, duration_minutes, now_ms=0):
        if duration_minutes <= 0:
            self.cancel_timer()
            return
        self.timer_end_time_ = now_ms + int(duration_minutes * 60 * 1000)
        self.timer_active_ = True
        self.timer_turning_off_ = False
        self._log("I", f"Sleep timer set for {duration_minutes:.0f} minutes")

    def cancel_timer(self):
        if self.timer_active_:
            self.timer_active_ = False
            self._log("I", "Sleep timer cancelled")

    def loop_tick(self, now_ms):
        """Check timer expiry. Returns True if timer fired and OFF was requested."""
        if not self.timer_active_:
            return False
        if now_ms >= self.timer_end_time_:
            self._log("I", f"Sleep timer expired - turning unit OFF")
            self.timer_active_ = False
            self.timer_turning_off_ = True
            self.control(mode=MODE_OFF)
            return True
        return False
