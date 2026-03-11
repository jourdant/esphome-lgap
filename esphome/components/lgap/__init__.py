import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.cpp_helpers import gpio_pin_expression
from esphome.components import uart, sensor
from esphome.const import (
    CONF_ID,
    CONF_NAME,
    UNIT_KILOWATT,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
)
from esphome import pins

DEPENDENCIES = ["uart", "sensor"]
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
CONF_COOLING_MAX_POWER = "cooling_max_power"
CONF_HEATING_MAX_POWER = "heating_max_power"
CONF_POWER_MULTIPLIER = "power_multiplier"
CONF_TOTAL_POWER_SENSOR = "total_power_sensor"

#build schema
CONFIG_SCHEMA = uart.UART_DEVICE_SCHEMA.extend(
    {
        cv.GenerateID(): cv.declare_id(LGAP),
        cv.Optional(CONF_FLOW_CONTROL_PIN): pins.gpio_output_pin_schema,
        cv.Optional(CONF_RECEIVE_WAIT_TIME, default="500ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_LOOP_WAIT_TIME, default="500ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_TX_BYTE_0, default=0x80): cv.hex_uint8_t,
        cv.Optional(CONF_COOLING_MAX_POWER, default=5.86): cv.float_range(min=0.1, max=20.0),
        cv.Optional(CONF_HEATING_MAX_POWER, default=6.19): cv.float_range(min=0.1, max=20.0),
        cv.Optional(CONF_POWER_MULTIPLIER, default=1.0): cv.float_range(min=0.1, max=5.0),
        cv.Optional(CONF_TOTAL_POWER_SENSOR): sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOWATT,
            accuracy_decimals=2,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
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
    
    #power estimation parameters
    cg.add(var.set_cooling_max_power(config[CONF_COOLING_MAX_POWER]))
    cg.add(var.set_heating_max_power(config[CONF_HEATING_MAX_POWER]))
    cg.add(var.set_power_multiplier(config[CONF_POWER_MULTIPLIER]))
    
    #total power sensor - auto-generate if not explicitly configured
    if CONF_TOTAL_POWER_SENSOR in config:
        sens = await sensor.new_sensor(config[CONF_TOTAL_POWER_SENSOR])
        cg.add(var.set_total_power_sensor(sens))
    else:
        # Auto-generate total power sensor with simple name
        from esphome.core import ID
        lgap_id = config[CONF_ID].id
        total_power_id = ID(f"{lgap_id}_total_power", is_manual=False, type=sensor.Sensor)
        
        # Build and validate config using sensor_schema to get all defaults
        sensor_config_schema = sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOWATT,
            accuracy_decimals=2,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        )
        total_power_config = sensor_config_schema({
            CONF_ID: total_power_id,
            CONF_NAME: "Total System Power",
        })
        
        sens = await sensor.new_sensor(total_power_config)
        cg.add(var.set_total_power_sensor(sens))
