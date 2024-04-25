#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

#include "../lgap.h"
#include "lgap_climate.h"

namespace esphome
{
  namespace lgap
  {

    static const char *const TAG = "lgap.climate";
    static const u_int8_t MIN_TEMPERATURE = 16;
    static const u_int8_t MAX_TEMPERATURE = 36;

    void LGAPHVACClimate::dump_config()
    {
      ESP_LOGCONFIG(TAG, "LGAP HVAC:");
      ESP_LOGCONFIG(TAG, "  Zone Number: %d", this->zone_number);
      ESP_LOGCONFIG(TAG, "  Mode: %d", (int)this->mode);
      ESP_LOGCONFIG(TAG, "  Swing: %d", (int)this->swing_mode);
      ESP_LOGCONFIG(TAG, "  Temperature: %d", this->target_temperature);
    }



    void LGAPHVACClimate::setup()
    {
      ESP_LOGCONFIG(TAG, "setup() setting initial HVAC state...");

      // restore set points
      auto restore = this->restore_state_();
      if (restore.has_value())
      {
        ESP_LOGCONFIG(TAG, "Restoring original state...");
        restore->apply(this);
      }
      else
      {
        ESP_LOGCONFIG(TAG, "Creating new state...");
        // restore from defaults
        this->mode = climate::CLIMATE_MODE_OFF;

        // initialize target temperature to some value so that it's not NAN
        this->target_temperature = roundf(clamp(this->current_temperature, (float)MIN_TEMPERATURE, (float)MAX_TEMPERATURE));
        this->fan_mode = climate::CLIMATE_FAN_AUTO;
        this->swing_mode = climate::CLIMATE_SWING_OFF;
        this->preset = climate::CLIMATE_PRESET_NONE;
      }

      // Never send nan to HA
      if (std::isnan(this->target_temperature))
      {
        this->target_temperature = 24;
      }

      // todo: initialise the current temp too
    }

    esphome::climate::ClimateTraits LGAPHVACClimate::traits()
    {
      auto traits = climate::ClimateTraits();
      traits.set_supports_current_temperature(true);
      traits.set_supports_two_point_target_temperature(false);
      traits.set_supports_current_humidity(false);
      traits.set_supports_target_humidity(false);

      traits.set_supported_modes({
          climate::CLIMATE_MODE_OFF,
          climate::CLIMATE_MODE_HEAT,
          climate::CLIMATE_MODE_DRY,
          climate::CLIMATE_MODE_COOL,
          climate::CLIMATE_MODE_FAN_ONLY,
          climate::CLIMATE_MODE_HEAT_COOL,
      });

      traits.set_supported_fan_modes({
          climate::CLIMATE_FAN_LOW,
          climate::CLIMATE_FAN_MEDIUM,
          climate::CLIMATE_FAN_HIGH,
      });

      traits.set_supported_swing_modes({
          climate::CLIMATE_SWING_OFF,
          climate::CLIMATE_SWING_VERTICAL,
      });

      // todo: validate these min/max numbers
      traits.set_visual_min_temperature(MIN_TEMPERATURE);
      traits.set_visual_max_temperature(MAX_TEMPERATURE);
      traits.set_visual_temperature_step(1);
      return traits;
    }

    void LGAPHVACClimate::control(const esphome::climate::ClimateCall &call)
    {
      ESP_LOGV(TAG, "esphome::climate::ClimateCall");

      // mode
      if (call.get_mode().has_value())
      {
        ESP_LOGV(TAG, "Mode change requested");
        climate::ClimateMode mode = *call.get_mode();

        // mode - LGAP has a separate state for power and for mode. HA combines them into a single entity
        // anything that is not Off, needs to also set the power mode to On
        if (this->mode != mode)
        {

          if (mode == climate::CLIMATE_MODE_OFF)
          {
            this->power_state_ = 0;
          }
          else if (mode == climate::CLIMATE_MODE_HEAT)
          {
            this->power_state_ = 1;
            this->mode_ = 4;
          }
          else if (mode == climate::CLIMATE_MODE_DRY)
          {
            this->power_state_ = 1;
            this->mode_ = 1;
          }
          else if (mode == climate::CLIMATE_MODE_COOL)
          {
            this->power_state_ = 1;
            this->mode_ = 0;
          }
          else if (mode == climate::CLIMATE_MODE_FAN_ONLY)
          {
            this->power_state_ = 1;
            this->mode_ = 2;
          }
          else if (mode == climate::CLIMATE_MODE_HEAT_COOL)
          {
            this->power_state_ = 1;
            this->mode_ = 3;
          }
        }

        // Publish updated state
        this->write_update_pending = true;
        this->mode = mode;
        this->publish_state();
      }

      // fan speed
      if (call.get_fan_mode().has_value())
      {
        ESP_LOGV(TAG, "Fan speed change requested");
        climate::ClimateFanMode fan_mode = *call.get_fan_mode();

        if (this->fan_mode != fan_mode)
        {
          if (fan_mode == climate::CLIMATE_FAN_AUTO)
          {
            // auto fan is actually not supported right now, so we set it to Low
            this->fan_speed_ = 0;
          }
          else if (fan_mode == climate::CLIMATE_FAN_LOW)
          {
            this->fan_speed_ = 0;
          }
          else if (fan_mode == climate::CLIMATE_FAN_MEDIUM)
          {
            this->fan_speed_ = 1;
          }
          else if (fan_mode == climate::CLIMATE_FAN_HIGH)
          {
            this->fan_speed_ = 2;
          }

          // publish state
          this->write_update_pending = true;
          this->fan_mode = fan_mode;
          this->publish_state();
        }
      }

      // swing
      if (call.get_swing_mode().has_value())
      {
        ESP_LOGV(TAG, "Swing mode change requested");
        climate::ClimateSwingMode swing_mode = *call.get_swing_mode();

        if (this->swing_mode != swing_mode)
        {
          if (swing_mode == climate::CLIMATE_SWING_OFF)
          {
            this->swing_ = 0;
          }
          else if (swing_mode == climate::CLIMATE_SWING_VERTICAL)
          {
            this->swing_ = 1;
          }

          // publish state
          this->write_update_pending = true;
          this->swing_mode = swing_mode;
          this->publish_state();
        }
      }

      // target temperature
      if (call.get_target_temperature().has_value())
      {
        // TODO: enable precision decimals as a yaml setting
        ESP_LOGV(TAG, "Temperature change requested");
        float temp = *call.get_target_temperature();
        if (temp != this->target_temperature_)
        {
          this->target_temperature_ = temp;
          this->target_temperature = temp;
        }

        this->write_update_pending = true;
        this->publish_state();
      }
    }

    void LGAPHVACClimate::handle_generate_lgap_request(std::vector<uint8_t> &message, uint8_t request_id)
    {
      // only create a write request if there is a pending message
      int write_state = this->write_update_pending ? 2 : 0;

      // build payload in message buffer
      message.push_back(128);
      message.push_back(111);
      message.push_back(request_id);
      message.push_back(this->zone_number);
      message.push_back(write_state | this->power_state_);
      message.push_back(this->mode_ | (this->swing_ << 3) | (this->fan_speed_ << 4));
      message.push_back((uint8_t)(this->target_temperature_ - 15));

      // blank val for checksum then replace with calculation
      message.push_back(0);
      message[7] = this->parent_->calculate_checksum(message);
    }

    // todo: add handling for when mode change is requested but mode is already on with another zone, ie can't choose heat when cool is already on
    void LGAPHVACClimate::handle_on_message_received(std::vector<uint8_t> &message)
    {
      ESP_LOGV(TAG, "LGAP message received");

      // handle bad class config
      if (this->zone_number < 0)
        return;
      if (message[4] != zone_number)
        return;

      bool publish_update = false;

      // process clean message as checksum already checked before reaching this point
      uint8_t power_state = (message[1] & 1);
      uint8_t mode = (message[6] & 7);

      // power state and mode
      // home assistant climate treats them as a single entity
      // this logic combines them from lgap into a single entity
      if (power_state != this->power_state_ || mode != this->mode_)
      {
        //handle mode
        if (mode == 0)
        {
          this->mode = climate::CLIMATE_MODE_COOL;
        }
        else if (mode == 1)
        {
          this->mode = climate::CLIMATE_MODE_DRY;
        }
        else if (mode == 2)
        {
          this->mode = climate::CLIMATE_MODE_FAN_ONLY;
        }
        else if (mode == 3)
        {
          // heat/cool is essentially auto
          this->mode = climate::CLIMATE_MODE_HEAT_COOL;
        }
        else if (mode == 4)
        {
          this->mode = climate::CLIMATE_MODE_HEAT;
        }
        else
        {
          ESP_LOGE(TAG, "Invalid mode received: %d", mode);
          this->mode = climate::CLIMATE_MODE_OFF;
        }

        //handle power state
        if (power_state == 0)
        {
          this->mode = climate::CLIMATE_MODE_OFF;
        }

        // update state
        publish_update = true;
        this->mode_ = mode;
        this->power_state_ = power_state;
      }

      // swing options
      uint8_t swing = (message[6] >> 3) & 1;
      if (swing != this->swing_)
      {
        if (swing == 0)
        {
          this->swing_mode = climate::CLIMATE_SWING_OFF;
        }
        else if (swing == 1)
        {
          this->swing_mode = climate::CLIMATE_SWING_VERTICAL;
        }
        else
        {
          ESP_LOGE(TAG, "Invalid swing received: %d", swing);
        }

        //update state
        this->swing_ = swing;
        publish_update = true;
      }

      // fan speed
      uint8_t fan_speed = ((message[6] >> 4) & 7);
      if (fan_speed != this->fan_speed_)
      {
        if (fan_speed == 0)
        {
          this->fan_mode = climate::CLIMATE_FAN_LOW;
        }
        else if (fan_speed == 1)
        {
          this->fan_mode = climate::CLIMATE_FAN_MEDIUM;
        }
        else if (fan_speed == 2)
        {
          this->fan_mode = climate::CLIMATE_FAN_HIGH;
        }
        else
        {
          ESP_LOGE(TAG, "Invalid fan speed received: %d", fan_speed);
        }

        //update state
        this->fan_speed_ = fan_speed;
        publish_update = true;
      }

      // target temp
      int target_temperature = (message[7] & 0xf) + 15;
      if (target_temperature != this->target_temperature_)
      {
        this->target_temperature_ = target_temperature;
        this->target_temperature = target_temperature;
        publish_update = true;
      }

      // current temp
      //TODO: implement precision setting for reported temperature
      int current_temperature = std::roundf((70 - message[8] * 100.0 / 256.0)) / 100.0;
      if (current_temperature != this->current_temperature_)
      {
        this->current_temperature_ = current_temperature;
        this->current_temperature = current_temperature;
        publish_update = true;
      }

      // send update to home assistant with all the changed variables
      if (publish_update == true)
      {
        this->publish_state();
      }
    }
  } // namespace lgap
} // namespace esphome