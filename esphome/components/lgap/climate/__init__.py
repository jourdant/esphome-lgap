import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import climate, sensor
from esphome.const import (
    CONF_ID,
    CONF_NAME,
    UNIT_KILOWATT,
    UNIT_CELSIUS,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
)
from .. import (
    lgap_ns,
    LGAP,
    CONF_LGAP_ID
)

DEPENDENCIES = ["lgap"]
CODEOWNERS = ["@jourdant"]

LGAP_HVAC_Climate = lgap_ns.class_("LGAPHVACClimate", cg.Component, climate.Climate)

CONF_ZONE_NUMBER = "zone"
CONF_TEMPERATURE_PUBISH_TIME = "temperature_publish_time"
CONF_POWER_SENSOR = "power_sensor"
CONF_LOAD_BYTE_SENSOR = "load_byte_sensor"
CONF_PIPE_IN_SENSOR = "pipe_in_sensor"
CONF_PIPE_OUT_SENSOR = "pipe_out_sensor"

CONFIG_SCHEMA = climate.CLIMATE_SCHEMA.extend(
    {
        cv.GenerateID(): cv.declare_id(LGAP_HVAC_Climate),
        cv.GenerateID(CONF_LGAP_ID): cv.use_id(LGAP),
        cv.Optional(CONF_ZONE_NUMBER, default=0): cv.All(cv.int_),
        cv.Optional(CONF_TEMPERATURE_PUBISH_TIME, default="300000ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_POWER_SENSOR): sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOWATT,
            accuracy_decimals=2,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_LOAD_BYTE_SENSOR): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PIPE_IN_SENSOR): sensor.sensor_schema(
            unit_of_measurement=UNIT_CELSIUS,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_PIPE_OUT_SENSOR): sensor.sensor_schema(
            unit_of_measurement=UNIT_CELSIUS,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    #register against climate to make it available in home assistant
    await climate.register_climate(var, config)

    #retrieve parent lgap component and register climate device
    lgap = await cg.get_variable(config[CONF_LGAP_ID])
    cg.add(lgap.register_device(var))
    cg.add(var.set_parent(lgap))

    #set properties of the climate component
    cg.add(var.set_zone_number(config[CONF_ZONE_NUMBER]))
    cg.add(var.set_temperature_publish_time(config[CONF_TEMPERATURE_PUBISH_TIME]))
    
    #set power sensor - auto-generate name if not explicitly configured
    if CONF_POWER_SENSOR in config:
        sens = await sensor.new_sensor(config[CONF_POWER_SENSOR])
        cg.add(var.set_power_sensor(sens))
    else:
        # Auto-generate power sensor based on climate ID and name
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        power_id = ID(f"{climate_id}_power", is_manual=False, type=sensor.Sensor)
        
        # Use climate name if available, otherwise derive from ID
        if CONF_NAME in config:
            sensor_name = f"{config[CONF_NAME]} Power"
        else:
            # Convert ID to human-readable name (e.g., "zone_0_climate" -> "Zone 0 Climate Power")
            friendly_name = climate_id.replace("_", " ").title()
            sensor_name = f"{friendly_name} Power"
        
        # Build and validate config using sensor_schema to get all defaults
        sensor_config_schema = sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOWATT,
            accuracy_decimals=2,
            device_class=DEVICE_CLASS_POWER,
            state_class=STATE_CLASS_MEASUREMENT,
        )
        power_config = sensor_config_schema({
            CONF_ID: power_id,
            CONF_NAME: sensor_name,
        })
        
        sens = await sensor.new_sensor(power_config)
        cg.add(var.set_power_sensor(sens))
    
    #set load byte sensor - auto-generate name if not explicitly configured
    if CONF_LOAD_BYTE_SENSOR in config:
        sens = await sensor.new_sensor(config[CONF_LOAD_BYTE_SENSOR])
        cg.add(var.set_load_byte_sensor(sens))
    else:
        # Auto-generate load byte sensor based on climate ID and name
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        load_byte_id = ID(f"{climate_id}_load_byte", is_manual=False, type=sensor.Sensor)
        
        # Use climate name if available, otherwise derive from ID
        if CONF_NAME in config:
            sensor_name = f"{config[CONF_NAME]} Load Byte"
        else:
            # Convert ID to human-readable name (e.g., "zone_0_climate" -> "Zone 0 Climate Load Byte")
            friendly_name = climate_id.replace("_", " ").title()
            sensor_name = f"{friendly_name} Load Byte"
        
        # Build and validate config using sensor_schema to get all defaults
        sensor_config_schema = sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        )
        load_byte_config = sensor_config_schema({
            CONF_ID: load_byte_id,
            CONF_NAME: sensor_name,
        })
        
        sens = await sensor.new_sensor(load_byte_config)
        cg.add(var.set_load_byte_sensor(sens))
    
    # Set pipe-in temperature sensor - auto-generate name if not explicitly configured
    if CONF_PIPE_IN_SENSOR in config:
        sens = await sensor.new_sensor(config[CONF_PIPE_IN_SENSOR])
        cg.add(var.set_pipe_in_sensor(sens))
    else:
        # Auto-generate pipe-in sensor based on climate ID and name
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        pipe_in_id = ID(f"{climate_id}_pipe_in", is_manual=False, type=sensor.Sensor)
        
        # Use climate name if available, otherwise derive from ID
        if CONF_NAME in config:
            sensor_name = f"{config[CONF_NAME]} Pipe In"
        else:
            # Convert ID to human-readable name
            friendly_name = climate_id.replace("_", " ").title()
            sensor_name = f"{friendly_name} Pipe In"
        
        # Build and validate config using sensor_schema to get all defaults
        sensor_config_schema = sensor.sensor_schema(
            unit_of_measurement=UNIT_CELSIUS,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        )
        pipe_in_config = sensor_config_schema({
            CONF_ID: pipe_in_id,
            CONF_NAME: sensor_name,
        })
        
        sens = await sensor.new_sensor(pipe_in_config)
        cg.add(var.set_pipe_in_sensor(sens))
    
    # Set pipe-out temperature sensor - auto-generate name if not explicitly configured
    if CONF_PIPE_OUT_SENSOR in config:
        sens = await sensor.new_sensor(config[CONF_PIPE_OUT_SENSOR])
        cg.add(var.set_pipe_out_sensor(sens))
    else:
        # Auto-generate pipe-out sensor based on climate ID and name
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        pipe_out_id = ID(f"{climate_id}_pipe_out", is_manual=False, type=sensor.Sensor)
        
        # Use climate name if available, otherwise derive from ID
        if CONF_NAME in config:
            sensor_name = f"{config[CONF_NAME]} Pipe Out"
        else:
            # Convert ID to human-readable name
            friendly_name = climate_id.replace("_", " ").title()
            sensor_name = f"{friendly_name} Pipe Out"
        
        # Build and validate config using sensor_schema to get all defaults
        sensor_config_schema = sensor.sensor_schema(
            unit_of_measurement=UNIT_CELSIUS,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_TEMPERATURE,
            state_class=STATE_CLASS_MEASUREMENT,
        )
        pipe_out_config = sensor_config_schema({
            CONF_ID: pipe_out_id,
            CONF_NAME: sensor_name,
        })
        
        sens = await sensor.new_sensor(pipe_out_config)
        cg.add(var.set_pipe_out_sensor(sens))
    
