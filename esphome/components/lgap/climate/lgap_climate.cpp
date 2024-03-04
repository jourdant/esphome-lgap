#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

#include "../lgap.h"
#include "lgap_climate.h"

namespace esphome
{
  namespace lgap
  {

    static const char *const TAG = "lgap.climate";

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
      if (restore.has_value()) {
        ESP_LOGCONFIG(TAG, "Restoring original state...");
        restore->apply(this);
      } else {
        ESP_LOGCONFIG(TAG, "Creating new state...");
        // restore from defaults
        this->mode = climate::CLIMATE_MODE_OFF;

        // initialize target temperature to some value so that it's not NAN
        this->target_temperature = roundf(clamp(this->current_temperature, 16.0f, 34.0f));
        this->fan_mode = climate::CLIMATE_FAN_AUTO;
        this->swing_mode = climate::CLIMATE_SWING_OFF;
        this->preset = climate::CLIMATE_PRESET_NONE;
      }

      // Never send nan to HA
      if (std::isnan(this->target_temperature)) {
        this->target_temperature = 24;
      }
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
          // todo: validate this comment
          // Adding this leads to esphome data not showing on Home Assistant somehow, hence skipping. Others please try and let me know
      });

      traits.set_supported_fan_modes({
          climate::CLIMATE_FAN_AUTO,
          climate::CLIMATE_FAN_LOW,
          climate::CLIMATE_FAN_MEDIUM,
          climate::CLIMATE_FAN_HIGH,
      });

      traits.set_supported_swing_modes({
          climate::CLIMATE_SWING_OFF,
          climate::CLIMATE_SWING_VERTICAL,
      });

      // todo: validate these min/max numbers
      traits.set_visual_min_temperature(16);
      traits.set_visual_max_temperature(34);
      traits.set_visual_temperature_step(1);
      return traits;
    }

    void LGAPHVACClimate::control(const esphome::climate::ClimateCall &call)
    {
      ESP_LOGV(TAG, "Control called");

      // mode
      if (call.get_mode().has_value())
      {
        ESP_LOGV(TAG, "Mode change requested");

        // User requested mode change
        climate::ClimateMode mode = *call.get_mode();

        if (mode == climate::CLIMATE_MODE_OFF && this->mode != mode)
        {
          this->power_state_ = 0;
          this->write_update_pending = true;
        }
        else if (mode == climate::CLIMATE_MODE_HEAT && this->mode != mode)
        {
          this->power_state_ = 1;
          this->mode_ = 4;
          this->write_update_pending = true;
        }
        else if (mode == climate::CLIMATE_MODE_DRY && this->mode != mode)
        {
          this->power_state_ = 1;
          this->mode_ = 1;
          this->write_update_pending = true;
        }
        else if (mode == climate::CLIMATE_MODE_COOL && this->mode != mode)
        {
          this->power_state_ = 1;
          this->mode_ = 0;
          this->write_update_pending = true;
        }
        else if (mode == climate::CLIMATE_MODE_FAN_ONLY && this->mode != mode)
        {
          this->power_state_ = 1;
          this->mode_ = 2;
          this->write_update_pending = true;
        }
        else if (mode == climate::CLIMATE_MODE_HEAT_COOL && this->mode != mode)
        {
          this->power_state_ = 1;
          this->mode_ = 3;
          this->write_update_pending = true;
        }

        // Publish updated state
        this->mode = mode;
        this->publish_state();
      }

      // fan speed
      if (call.get_fan_mode().has_value())
      {
        ESP_LOGV(TAG, "Fan speed change requested");

        // User requested fan mode change
        climate::ClimateFanMode fan_mode = *call.get_fan_mode();

        if (fan_mode == climate::CLIMATE_FAN_AUTO && this->fan_mode != fan_mode)
        {
          // auto fan is actually not supported right now
          this->fan_speed_ = 0;
          this->write_update_pending = true;
        }
        else if (fan_mode == climate::CLIMATE_FAN_LOW && this->fan_mode != fan_mode)
        {
          this->fan_speed_ = 0;
          this->write_update_pending = true;
        }
        else if (fan_mode == climate::CLIMATE_FAN_MEDIUM && this->fan_mode != fan_mode)
        {
          this->fan_speed_ = 1;
          this->write_update_pending = true;
        }
        else if (fan_mode == climate::CLIMATE_FAN_HIGH && this->fan_mode != fan_mode)
        {
          this->fan_speed_ = 2;
          this->write_update_pending = true;
        }

        this->fan_mode = fan_mode;
        this->publish_state();
      }

      // swing
      if (call.get_swing_mode().has_value())
      {
        ESP_LOGV(TAG, "Swing mode change requested");

        // User requested fan mode change
        climate::ClimateSwingMode swing_mode = *call.get_swing_mode();
        // Send fan mode to hardware
        if (swing_mode == climate::CLIMATE_SWING_OFF && this->swing_mode != swing_mode)
        {
          this->swing_ = 0;
          this->write_update_pending = true;
        }
        else if (swing_mode == climate::CLIMATE_SWING_VERTICAL && this->swing_mode != swing_mode)
        {
          this->swing_ = 1;
          this->write_update_pending = true;
        }

        this->swing_mode = swing_mode;
        this->publish_state();
      }

      // temperature
      if (call.get_target_temperature().has_value())
      {
        ESP_LOGV(TAG, "Temperature change requested");

        // User requested target temperature change
        float temp = *call.get_target_temperature();
        if (temp != this->target_temperature_)
        {
          this->target_temperature_ = temp;
          this->target_temperature = temp;
          this->write_update_pending = true;
        }
        this->publish_state();
      }
    }

    void LGAPHVACClimate::handle_generate_lgap_request(std::vector<unsigned char> &message)
    {
      //only create a write request if there is a pending message
      int write_state = this->write_update_pending ? 2 : 0;

      //build payload in message buffer
      message.push_back(0);
      message.push_back(0);
      message.push_back(0);
      message.push_back(this->zone_number);
      message.push_back(write_state | this->power_state_);
      message.push_back(this->mode_ | (this->swing_ << 3) | (this->fan_speed_ << 4));
      message.push_back((int)this->target_temperature_ - 15);

      // blank val for checksum
      message.push_back(0);
      message[7] = this->parent_->calculate_checksum(message);
    }

    void LGAPHVACClimate::handle_on_message_received(std::vector<unsigned char> &message)
    {
      ESP_LOGV(TAG, "LGAP message received");

      // handle bad class config
      if (this->zone_number < 0)
        return;
      if (message[4] != zone_number)
        return;

      bool publish_update = false;

      // process clean message as checksum already checked before reaching this point
      unsigned char power_state = (message[1] & 1);
      unsigned char mode = (message[6] & 7);

      //power state and mode
      //home assistant climate treats them as a single entity
      //this logic combines them from lgap into a single entity
      if (power_state != this->power_state_ || mode != this->mode_) {
        this->power_state_ = power_state;
        this->mode_ = mode;
        publish_update = true;

        if (this->mode_ == 0) {
          this->mode = climate::CLIMATE_MODE_COOL;
        } else if (this->mode_ == 1) {
          this->mode = climate::CLIMATE_MODE_DRY;
        } else if (this->mode_ == 2) {
          this->mode = climate::CLIMATE_MODE_FAN_ONLY;
        } else if (this->mode_ == 3) {
          this->mode = climate::CLIMATE_MODE_HEAT_COOL;
        } else if (this->mode_ == 4) {
          this->mode = climate::CLIMATE_MODE_HEAT;
        }
        else {
          ESP_LOGE(TAG, "Invalid mode received: %d", this->mode_);
        }
      } else {
        this->mode = climate::CLIMATE_MODE_OFF;
      }

      //swing options
      unsigned char swing = (message[6] >> 3) & 1;
      if (swing != this->swing_) {
        this->swing_ = swing;
        publish_update = true;

        if (this->swing_ == 0) {
          this->swing_mode = climate::CLIMATE_SWING_OFF;
        } else if (this->swing_ == 1) {
          this->swing_mode = climate::CLIMATE_SWING_VERTICAL;
        }
        else {
          ESP_LOGE(TAG, "Invalid swing received: %d", this->swing_);
        }
      }

      //fan speed
      unsigned char fan_speed = ((message[6] >> 4) & 7);
      if (fan_speed != this->fan_speed_) {
        this->fan_speed_ = fan_speed;
        publish_update = true;

        if (this->fan_speed_ == 0) {
          this->fan_mode = climate::CLIMATE_FAN_LOW;
        } else if (this->fan_speed_ == 1) {
          this->fan_mode = climate::CLIMATE_FAN_MEDIUM;
        } else if (this->fan_speed_ == 2) {
          this->fan_mode = climate::CLIMATE_FAN_HIGH;
        }
        else {
          ESP_LOGE(TAG, "Invalid fan speed received: %d", this->fan_speed_);
        }
      }

      //target temp
      float target_temperature = (message[7] & 0xf) + 15;
      if (target_temperature != this->target_temperature_) {
        this->target_temperature_ = target_temperature;
        this->target_temperature = target_temperature;
        publish_update = true;
      }

      //current temp
      float current_temperature = std::round((70 - message[8] * 100.0 / 256.0) * 100) / 100.0;
      if (current_temperature != this->current_temperature_) {
        this->current_temperature_ = current_temperature;
        this->current_temperature = current_temperature;
        publish_update = true;
      }

      //send update to home assistant with all the changed variables
      if (publish_update == true) {
        this->publish_state();
      }
    }
  } // namespace lgap
} // namespace esphome