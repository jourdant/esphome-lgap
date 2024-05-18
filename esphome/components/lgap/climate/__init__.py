import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import climate
from esphome.const import (
    CONF_ID,
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

CONFIG_SCHEMA = climate.CLIMATE_SCHEMA.extend(
    {
        cv.GenerateID(): cv.declare_id(LGAP_HVAC_Climate),
        cv.GenerateID(CONF_LGAP_ID): cv.use_id(LGAP),
        cv.Optional(CONF_ZONE_NUMBER, default=0): cv.All(cv.int_),
        cv.Optional(CONF_TEMPERATURE_PUBISH_TIME, default="300000ms"): cv.positive_time_period_milliseconds,
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
    
