"""
LGAP bus simulator: models the AC indoor unit, wall panel, and polling loop.
"""

from .lgap_model import LGAPClimateModel, MODE_OFF, MODE_COOL, LGAP_MODE


class ACUnit:
    """Models the physical AC indoor unit's state."""

    def __init__(self):
        self.power_state = 0
        self.mode = 0  # LGAP mode value (0=COOL, etc.)
        self.fan_speed = 4  # AUTO
        self.target_temperature = 24.0

    def process_request(self, is_write, payload):
        """Process a READ or WRITE from the ESP. Returns response state."""
        if is_write:
            self.power_state = payload["power_state"]
            self.mode = payload["mode"]
            self.fan_speed = payload["fan_speed"]
            self.target_temperature = payload["target_temperature"]

        return {
            "power_state": self.power_state,
            "mode": self.mode,
            "fan_speed": self.fan_speed,
            "target_temperature": self.target_temperature,
        }


class WallPanel:
    """Models the physical wall panel controller."""

    def __init__(self, ac: ACUnit):
        self.ac = ac

    def set_temperature(self, temp):
        """User changes temperature at wall panel."""
        self.ac.target_temperature = temp

    def set_mode(self, lgap_mode, power=1):
        """User changes mode at wall panel."""
        self.ac.mode = lgap_mode
        self.ac.power_state = power

    def set_fan_speed(self, fan_speed):
        """User changes fan speed at wall panel."""
        self.ac.fan_speed = fan_speed

    def turn_off(self):
        """User turns off AC at wall panel."""
        self.ac.power_state = 0

    def turn_on(self, lgap_mode=0):
        """User turns on AC at wall panel."""
        self.ac.power_state = 1
        self.ac.mode = lgap_mode


class Simulation:
    """
    Orchestrates the LGAP polling loop between ESP, AC, and wall panel.
    Each 'cycle' is one poll: ESP generates request → AC responds → ESP processes.
    """

    def __init__(self):
        self.esp = LGAPClimateModel()
        self.ac = ACUnit()
        self.wall_panel = WallPanel(self.ac)
        self.cycle_count = 0

    def run_cycle(self):
        """Run one poll cycle: generate request → AC processes → ESP receives response."""
        is_write, payload = self.esp.generate_request()
        response = self.ac.process_request(is_write, payload)
        self.esp.on_message_received(
            power_state=response["power_state"],
            mode=response["mode"],
            fan_speed=response["fan_speed"],
            target_temperature=response["target_temperature"],
        )
        self.cycle_count += 1

    def run_cycles(self, n):
        """Run multiple poll cycles."""
        for _ in range(n):
            self.run_cycle()

    def ha_command(self, **kwargs):
        """Send a command from Home Assistant."""
        self.esp.control(**kwargs)

    def ha_turn_on(self, mode=MODE_COOL, temperature=24.0):
        self.ha_command(mode=mode, temperature=temperature)

    def ha_turn_off(self):
        self.ha_command(mode=MODE_OFF)
