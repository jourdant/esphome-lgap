import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.cpp_helpers import gpio_pin_expression
from esphome.components import uart
from esphome.const import (
    CONF_ID,
)
from esphome import pins

DEPENDENCIES = ["uart", "sensor", "number", "switch"]
CODEOWNERS = ["@jourdant"]
MULTI_CONF = True

#class metadata
lgap_ns = cg.esphome_ns.namespace("lgap")
LGAP = lgap_ns.class_("LGAP", uart.UARTDevice, cg.Component)

#setting names
CONF_LGAP_ID = "lgap_id"
CONF_RECEIVE_WAIT_TIME = "receive_wait_time"
CONF_LOOP_WAIT_TIME = "loop_wait_time"
CONF_FLOW_CONTROL_PIN = "flow_control_pin"
CONF_TX_BYTE_0 = "tx_byte_0"

#build schema
CONFIG_SCHEMA = uart.UART_DEVICE_SCHEMA.extend(
    {
        cv.GenerateID(): cv.declare_id(LGAP),
        cv.Optional(CONF_FLOW_CONTROL_PIN): pins.gpio_output_pin_schema,
        cv.Optional(CONF_RECEIVE_WAIT_TIME, default="500ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_LOOP_WAIT_TIME, default="500ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_TX_BYTE_0, default=0x80): cv.hex_uint8_t,
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

    #times
    cg.add(var.set_receive_wait_time(config[CONF_RECEIVE_WAIT_TIME]))
    cg.add(var.set_loop_wait_time(config[CONF_LOOP_WAIT_TIME]))
    
    #first tx byte
    cg.add(var.set_tx_byte_0(config[CONF_TX_BYTE_0]))
