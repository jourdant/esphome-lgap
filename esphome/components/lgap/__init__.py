import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.cpp_helpers import gpio_pin_expression
from esphome.components import uart
from esphome.const import (
    CONF_ID,
)
from esphome import pins

DEPENDENCIES = ["uart"]
CODEOWNERS = ["@jourdant"]
MULTI_CONF = True

#class metadata
lgap_ns = cg.esphome_ns.namespace("lgap")
LGAP = lgap_ns.class_("LGAP", uart.UARTDevice, cg.Component)

#setting names
CONF_LGAP_ID = "lgap_id"
CONF_SEND_WAIT_TIME = "send_wait_time"
CONF_RECEIVE_WAIT_TIME = "receive_wait_time"
CONF_ZONE_CHECK_WAIT_TIME = "zone_check_wait_time"
CONF_FLOW_CONTROL_PIN = "flow_control_pin"

#debug flags
CONF_LOOP_WAIT_TIME = "loop_wait_time"
CONF_DEBUG  = "debug"

CONFIG_SCHEMA = uart.UART_DEVICE_SCHEMA.extend(
    {
        cv.GenerateID(): cv.declare_id(LGAP),
        cv.Optional(CONF_FLOW_CONTROL_PIN): pins.gpio_output_pin_schema,
        cv.Optional(CONF_SEND_WAIT_TIME, default="250ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_RECEIVE_WAIT_TIME, default="250ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_ZONE_CHECK_WAIT_TIME, default="1000ms"): cv.positive_time_period_milliseconds,

        #debug flags
        cv.Optional(CONF_DEBUG, default=False): cv.boolean,
        cv.Optional(CONF_LOOP_WAIT_TIME, default="250ms"): cv.positive_time_period_milliseconds,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    #register device
    cg.add_global(lgap_ns.using)
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    #connect this object to the parent uart device
    await uart.register_uart_device(var, config)

    #map properties from yaml to the c++ object
    if CONF_FLOW_CONTROL_PIN in config:
        pin = await gpio_pin_expression(config[CONF_FLOW_CONTROL_PIN])
        cg.add(var.set_flow_control_pin(pin))

    cg.add(var.set_send_wait_time(config[CONF_SEND_WAIT_TIME]))
    cg.add(var.set_receive_wait_time(config[CONF_RECEIVE_WAIT_TIME]))
    cg.add(var.set_zone_check_wait_time(config[CONF_ZONE_CHECK_WAIT_TIME]))

    #debug flags
    cg.add(var.set_debug(config[CONF_DEBUG]))
    cg.add(var.set_loop_wait_time(config[CONF_LOOP_WAIT_TIME]))