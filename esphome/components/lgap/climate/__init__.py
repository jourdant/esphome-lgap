import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import climate, sensor, number, switch
from esphome.const import (
    CONF_ID,
    CONF_NAME,
    UNIT_CELSIUS,
    UNIT_MINUTE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_DURATION,
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
TimerDurationNumber = lgap_ns.class_("TimerDurationNumber", number.Number)
ControlLockSwitch = lgap_ns.class_("ControlLockSwitch", switch.Switch)
LockTemperatureSwitch = lgap_ns.class_("LockTemperatureSwitch", switch.Switch)
LockFanSpeedSwitch = lgap_ns.class_("LockFanSpeedSwitch", switch.Switch)
LockModeSwitch = lgap_ns.class_("LockModeSwitch", switch.Switch)
PowerOnlyModeSwitch = lgap_ns.class_("PowerOnlyModeSwitch", switch.Switch)
PlasmaSwitch = lgap_ns.class_("PlasmaSwitch", switch.Switch)

CONF_ZONE_NUMBER = "zone"
CONF_TEMPERATURE_PUBISH_TIME = "temperature_publish_time"
CONF_SUPPORTS_AUTO_SWING = "supports_auto_swing"
CONF_SUPPORTS_AUTO_FAN = "supports_auto_fan"
CONF_SUPPORTS_QUIET_FAN = "supports_quiet_fan"
CONF_SUPPORTS_TURBO_FAN = "supports_turbo_fan"
CONF_SUPPORTS_PLASMA = "supports_plasma"
CONF_PLASMA = "plasma"
CONF_PIPE_IN_SENSOR = "pipe_in_sensor"
CONF_PIPE_OUT_SENSOR = "pipe_out_sensor"
CONF_ERROR_CODE_SENSOR = "error_code_sensor"
CONF_ZONE_ACTIVE_LOAD_SENSOR = "zone_active_load_sensor"
CONF_ZONE_POWER_STATE_SENSOR = "zone_power_state_sensor"
CONF_ZONE_DESIGN_LOAD_SENSOR = "zone_design_load_sensor"
CONF_ODU_TOTAL_LOAD_SENSOR = "odu_total_load_sensor"
CONF_SLEEP_TIMER = "sleep_timer"
CONF_TIMER_REMAINING = "timer_remaining"
CONF_CONTROL_LOCK = "control_lock"
CONF_LOCK_TEMPERATURE = "lock_temperature"
CONF_LOCK_FAN_SPEED = "lock_fan_speed"
CONF_LOCK_MODE = "lock_mode"
CONF_POWER_ONLY_MODE = "power_only_mode"

CONFIG_SCHEMA = climate.climate_schema(
    LGAP_HVAC_Climate
).extend(
    {
        cv.GenerateID(CONF_LGAP_ID): cv.use_id(LGAP),
        cv.Optional(CONF_ZONE_NUMBER, default=0): cv.All(cv.int_),
        cv.Optional(CONF_TEMPERATURE_PUBISH_TIME, default="300000ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_SUPPORTS_AUTO_SWING, default=False): cv.boolean,
        cv.Optional(CONF_SUPPORTS_AUTO_FAN, default=False): cv.boolean,
        cv.Optional(CONF_SUPPORTS_QUIET_FAN, default=False): cv.boolean,
        cv.Optional(CONF_SUPPORTS_TURBO_FAN, default=False): cv.boolean,
        cv.Optional(CONF_SUPPORTS_PLASMA, default=False): cv.boolean,
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
        cv.Optional(CONF_ERROR_CODE_SENSOR): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_ZONE_ACTIVE_LOAD_SENSOR): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_ZONE_POWER_STATE_SENSOR): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_ZONE_DESIGN_LOAD_SENSOR): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_ODU_TOTAL_LOAD_SENSOR): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_SLEEP_TIMER): number.number_schema(
            TimerDurationNumber,
            unit_of_measurement=UNIT_MINUTE,
            device_class=DEVICE_CLASS_DURATION,
        ),
        cv.Optional(CONF_TIMER_REMAINING): sensor.sensor_schema(
            unit_of_measurement=UNIT_MINUTE,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_DURATION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_CONTROL_LOCK): switch.switch_schema(
            ControlLockSwitch,
        ),
        cv.Optional(CONF_LOCK_TEMPERATURE): switch.switch_schema(
            LockTemperatureSwitch,
        ),
        cv.Optional(CONF_LOCK_FAN_SPEED): switch.switch_schema(
            LockFanSpeedSwitch,
        ),
        cv.Optional(CONF_LOCK_MODE): switch.switch_schema(
            LockModeSwitch,
        ),
        cv.Optional(CONF_POWER_ONLY_MODE): switch.switch_schema(
            PowerOnlyModeSwitch,
        ),
        cv.Optional(CONF_PLASMA): switch.switch_schema(
            PlasmaSwitch,
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
    cg.add(var.set_supports_auto_swing(config[CONF_SUPPORTS_AUTO_SWING]))
    cg.add(var.set_supports_auto_fan(config[CONF_SUPPORTS_AUTO_FAN]))
    cg.add(var.set_supports_quiet_fan(config[CONF_SUPPORTS_QUIET_FAN]))
    cg.add(var.set_supports_turbo_fan(config[CONF_SUPPORTS_TURBO_FAN]))
    cg.add(var.set_supports_plasma(config[CONF_SUPPORTS_PLASMA]))
    
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
    
    # Error code sensor - auto-generate if not explicitly configured
    if CONF_ERROR_CODE_SENSOR in config:
        sens = await sensor.new_sensor(config[CONF_ERROR_CODE_SENSOR])
        cg.add(var.set_error_code_sensor(sens))
    else:
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        sens_id = ID(f"{climate_id}_error_code", is_manual=False, type=sensor.Sensor)
        
        if CONF_NAME in config:
            sens_name = f"{config[CONF_NAME]} Error Code"
        else:
            friendly_name = climate_id.replace("_", " ").title()
            sens_name = f"{friendly_name} Error Code"
        
        sens_config = sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
        )({
            CONF_ID: sens_id,
            CONF_NAME: sens_name,
        })
        
        sens = await sensor.new_sensor(sens_config)
        cg.add(var.set_error_code_sensor(sens))
    
    # Auto-generate LonWorks-aligned load sensors
    # These track bytes in the 16-byte LGAP message matching LG's PI485→LonWorks mappings
    lonworks_load_sensors = [
        (CONF_ZONE_ACTIVE_LOAD_SENSOR, "set_zone_active_load_sensor", "zone_active_load", "Zone Active Load"),
        (CONF_ZONE_POWER_STATE_SENSOR, "set_zone_power_state_sensor", "zone_power_state", "Zone Power State"),
        (CONF_ZONE_DESIGN_LOAD_SENSOR, "set_zone_design_load_sensor", "zone_design_load", "Zone Design Load"),
        (CONF_ODU_TOTAL_LOAD_SENSOR, "set_odu_total_load_sensor", "odu_total_load", "ODU Total Load"),
    ]
    
    for conf_key, setter_method, id_suffix, name_suffix in lonworks_load_sensors:
        if conf_key in config:
            sens = await sensor.new_sensor(config[conf_key])
            cg.add(getattr(var, setter_method)(sens))
        else:
            # Auto-generate sensor
            from esphome.core import ID
            climate_id = config[CONF_ID].id
            sensor_id = ID(f"{climate_id}_{id_suffix}", is_manual=False, type=sensor.Sensor)
            
            # Use climate name if available, otherwise derive from ID
            if CONF_NAME in config:
                sensor_name = f"{config[CONF_NAME]} {name_suffix}"
            else:
                friendly_name = climate_id.replace("_", " ").title()
                sensor_name = f"{friendly_name} {name_suffix}"
            
            # Build and validate config
            sensor_config_schema = sensor.sensor_schema(
                accuracy_decimals=0,
                state_class=STATE_CLASS_MEASUREMENT,
            )
            sensor_config = sensor_config_schema({
                CONF_ID: sensor_id,
                CONF_NAME: sensor_name,
            })
            
            sens = await sensor.new_sensor(sensor_config)
            cg.add(getattr(var, setter_method)(sens))
    
    # Sleep timer - auto-generate if not explicitly configured
    # Automatic timer: set minutes to start, set to 0 to cancel
    if CONF_SLEEP_TIMER in config:
        num = cg.new_Pvariable(config[CONF_SLEEP_TIMER][CONF_ID])
        await number.register_number(num, config[CONF_SLEEP_TIMER], min_value=0, max_value=420, step=1)
        cg.add(var.set_timer_duration_number(num))
    else:
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        num_id = ID(f"{climate_id}_sleep_timer", is_manual=False, type=TimerDurationNumber)
        
        if CONF_NAME in config:
            num_name = f"{config[CONF_NAME]} Sleep Timer"
        else:
            friendly_name = climate_id.replace("_", " ").title()
            num_name = f"{friendly_name} Sleep Timer"
        
        num_config = number.number_schema(
            TimerDurationNumber,
            unit_of_measurement=UNIT_MINUTE,
            device_class=DEVICE_CLASS_DURATION,
        )({
            CONF_ID: num_id,
            CONF_NAME: num_name,
        })
        
        num = cg.new_Pvariable(num_id)
        await number.register_number(num, num_config, min_value=0, max_value=420, step=1)
        cg.add(var.set_timer_duration_number(num))
    
    # Timer remaining sensor (shows countdown)
    if CONF_TIMER_REMAINING in config:
        sens = await sensor.new_sensor(config[CONF_TIMER_REMAINING])
        cg.add(var.set_timer_remaining_sensor(sens))
    else:
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        sens_id = ID(f"{climate_id}_timer_remaining", is_manual=False, type=sensor.Sensor)
        
        if CONF_NAME in config:
            sens_name = f"{config[CONF_NAME]} Timer Remaining"
        else:
            friendly_name = climate_id.replace("_", " ").title()
            sens_name = f"{friendly_name} Timer Remaining"
        
        sens_config = sensor.sensor_schema(
            unit_of_measurement=UNIT_MINUTE,
            accuracy_decimals=1,
            device_class=DEVICE_CLASS_DURATION,
            state_class=STATE_CLASS_MEASUREMENT,
        )({
            CONF_ID: sens_id,
            CONF_NAME: sens_name,
        })
        
        sens = await sensor.new_sensor(sens_config)
        cg.add(var.set_timer_remaining_sensor(sens))
    
    # Control lock switch - auto-generate if not explicitly configured
    if CONF_CONTROL_LOCK in config:
        sw = cg.new_Pvariable(config[CONF_CONTROL_LOCK][CONF_ID])
        await switch.register_switch(sw, config[CONF_CONTROL_LOCK])
        cg.add(var.set_control_lock_switch(sw))
    else:
        from esphome.core import ID
        climate_id = config[CONF_ID].id
        sw_id = ID(f"{climate_id}_control_lock", is_manual=False, type=ControlLockSwitch)
        
        if CONF_NAME in config:
            sw_name = f"{config[CONF_NAME]} Control Lock"
        else:
            friendly_name = climate_id.replace("_", " ").title()
            sw_name = f"{friendly_name} Control Lock"
        
        sw_config = switch.switch_schema(ControlLockSwitch)({
            CONF_ID: sw_id,
            CONF_NAME: sw_name,
        })
        
        sw = cg.new_Pvariable(sw_id)
        await switch.register_switch(sw, sw_config)
        cg.add(var.set_control_lock_switch(sw))
    
    # Function restriction switches - auto-generate
    function_locks = [
        (CONF_LOCK_TEMPERATURE, LockTemperatureSwitch, "set_lock_temperature_switch", "lock_temperature", "Lock Temperature"),
        (CONF_LOCK_FAN_SPEED, LockFanSpeedSwitch, "set_lock_fan_speed_switch", "lock_fan_speed", "Lock Fan Speed"),
        (CONF_LOCK_MODE, LockModeSwitch, "set_lock_mode_switch", "lock_mode", "Lock Mode"),
        (CONF_POWER_ONLY_MODE, PowerOnlyModeSwitch, "set_power_only_mode_switch", "power_only_mode", "Power Only Mode"),
    ]
    
    for conf_key, switch_class, setter_method, id_suffix, name_suffix in function_locks:
        if conf_key in config:
            sw = cg.new_Pvariable(config[conf_key][CONF_ID])
            await switch.register_switch(sw, config[conf_key])
            cg.add(getattr(var, setter_method)(sw))
        else:
            from esphome.core import ID
            climate_id = config[CONF_ID].id
            sw_id = ID(f"{climate_id}_{id_suffix}", is_manual=False, type=switch_class)
            
            if CONF_NAME in config:
                sw_name = f"{config[CONF_NAME]} {name_suffix}"
            else:
                friendly_name = climate_id.replace("_", " ").title()
                sw_name = f"{friendly_name} {name_suffix}"
            
            sw_config = switch.switch_schema(switch_class)({
                CONF_ID: sw_id,
                CONF_NAME: sw_name,
            })
            
            sw = cg.new_Pvariable(sw_id)
            await switch.register_switch(sw, sw_config)
            cg.add(getattr(var, setter_method)(sw))
    
    # Plasma switch - only if feature is enabled
    if config[CONF_SUPPORTS_PLASMA]:
        if CONF_PLASMA in config:
            sw = cg.new_Pvariable(config[CONF_PLASMA][CONF_ID])
            await switch.register_switch(sw, config[CONF_PLASMA])
            cg.add(var.set_plasma_switch(sw))
        else:
            from esphome.core import ID
            climate_id = config[CONF_ID].id
            sw_id = ID(f"{climate_id}_plasma", is_manual=False, type=PlasmaSwitch)
            
            if CONF_NAME in config:
                sw_name = f"{config[CONF_NAME]} Plasma"
            else:
                friendly_name = climate_id.replace("_", " ").title()
                sw_name = f"{friendly_name} Plasma"
            
            sw_config = switch.switch_schema(PlasmaSwitch)({
                CONF_ID: sw_id,
                CONF_NAME: sw_name,
            })
            
            sw = cg.new_Pvariable(sw_id)
            await switch.register_switch(sw, sw_config)
            cg.add(var.set_plasma_switch(sw))
    
