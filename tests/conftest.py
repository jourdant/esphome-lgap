"""Shared pytest fixtures for LGAP climate tests."""

import pytest
from .simulator import Simulation
from .lgap_model import MODE_COOL, MODE_OFF


@pytest.fixture
def sim():
    """Fresh simulation with default state (AC off)."""
    return Simulation()


@pytest.fixture
def sim_on():
    """Simulation with AC already ON in COOL mode at 24°C, first state received."""
    s = Simulation()
    s.ac.power_state = 1
    s.ac.mode = 0  # COOL
    s.ac.target_temperature = 24.0
    s.ac.fan_speed = 4  # AUTO
    # Run one cycle so ESP picks up state and sets first_state_received_
    s.run_cycle()
    assert s.esp.first_state_received_
    assert s.esp.power_state_ == 1
    assert s.esp.mode == MODE_COOL
    return s


@pytest.fixture
def sim_on_locked_temp(sim_on):
    """AC ON with temperature lock enabled at 24°C."""
    sim_on.esp.lock_temperature_ = True
    return sim_on


@pytest.fixture
def sim_on_locked_mode(sim_on):
    """AC ON with mode lock enabled in COOL mode."""
    sim_on.esp.lock_mode_ = True
    return sim_on


@pytest.fixture
def sim_on_timer(sim_on):
    """AC ON with a 60-minute sleep timer configured and running."""
    sim_on.esp.timer_duration_minutes_ = 60.0
    sim_on.esp.start_timer(60.0, now_ms=0)
    return sim_on
