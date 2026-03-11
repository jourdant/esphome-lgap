#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

#include "../lgap.h"
#include "lgap_climate.h"

// LG LGAP Protocol Reference
// ============================
//
// FUNCTION LOCKS (Partial Lock Features):
// ========================================
// These locks prevent both Home Assistant AND wall controller changes.
// When a lock is active and a change is detected from the wall controller,
// ESPHome automatically reverts it by sending the previous value back.
//
// - Lock Temperature: Prevents temperature up/down changes
// - Lock Fan Speed: Prevents fan speed changes  
// - Lock Mode: Prevents mode changes (COOL↔HEAT↔etc)
// - Power Only Mode: Allows ONLY ON/OFF, locks temp/fan/mode
//
// Enforcement: Changes from wall controller trigger write_update_pending
// to send the original value back, effectively blocking the change.
//
// Control Flags (TX message[4] / RX message[1]):
//   bit0: ON (power state: 1=ON, 0=OFF)
//   bit1: EXE (execute write command)
//   bit2: Lock (control lock/child lock: 1=LOCKED, 0=UNLOCKED)
//   bit3: Reserved (0)
//   bit4: Plasma (air purification, optional)
//
// Error Code (message[5]):
//   0 = No error / normal operation
//   1-255 = Service codes from model's error code list
//   Check model documentation for specific error code meanings
//
// Mode (message[6] bits 0-2):
//   0 = COOL, 1 = DRY, 2 = FAN_ONLY, 3 = AUTO, 4 = HEAT
//
// Auto Swing (message[6] bit 3):
//   0 = OFF (manual airflow), 1 = AUTO (automatic airflow pattern)
//   Note: For ducted units, this controls software airflow logic, not physical vanes
//
// Fan Speed (message[6] bits 4-6):
//   0 = NO_CHANGE, 1 = LOW, 2 = MEDIUM, 3 = HIGH, 4 = AUTO
//   5 = SLOW (quiet), 6 = POWER/TURBO, 7 = SLOW+POWER (rare)
//
// Target Temp (message[7] lower nibble):
//   0-15 → Indoor set temp = value + 15°C (16-30°C range)
//
// Room Temp (message[8]):
//   0-255 raw → Temp(°C) = (192 - raw) / 3
//
// Pipe Temps (message[9], message[10]):
//   Same formula as room temp: Temp(°C) = (192 - raw) / 3
//
// Zone Active Load (message[11]):
//   0-255, typical idle: 204, under load: 80-220
//   LOWER value = HIGHER active load (inverse)
//
// Zone Power State (message[12]):
//   0 = RUNNING/ON, 1 = OFF/IDLE
//
// Zone Design Load (message[13]):
//   Constant per IDU design capacity (e.g., 9, 12, 24)
//
// ODU Total Load (message[14]):
//   ~Sum of design loads of ON zones, smoothed (0-255)

namespace esphome
{
  namespace lgap
  {

    static const char *const TAG = "lgap.climate";

    // Timer duration number implementation with automatic start/cancel
    void TimerDurationNumber::control(float value)
    {
      this->publish_state(value);
      
      if (this->parent_ != nullptr)
      {
        // Save the duration (timer will auto-start when AC turns ON)
        this->parent_->set_timer_duration_minutes(value);
        
        // If AC is currently ON and duration > 0, start timer now
        if (value > 0 && this->parent_->mode != climate::CLIMATE_MODE_OFF)
        {
          this->parent_->start_timer(value);
        }
        else if (value == 0)
        {
          // Duration set to 0 - cancel any active timer
          this->parent_->cancel_timer();
        }
      }
    }

    // Control lock switch implementation
    void ControlLockSwitch::write_state(bool state)
    {
      this->publish_state(state);
      
      if (this->parent_ != nullptr)
      {
        this->parent_->set_control_lock(state);
      }
    }

    // Function restriction switch implementations
    void LockTemperatureSwitch::write_state(bool state)
    {
      this->publish_state(state);
      if (this->parent_ != nullptr)
      {
        this->parent_->set_lock_temperature(state);
      }
    }

    void LockFanSpeedSwitch::write_state(bool state)
    {
      this->publish_state(state);
      if (this->parent_ != nullptr)
      {
        this->parent_->set_lock_fan_speed(state);
      }
    }

    void LockModeSwitch::write_state(bool state)
    {
      this->publish_state(state);
      if (this->parent_ != nullptr)
      {
        this->parent_->set_lock_mode(state);
      }
    }

    void PowerOnlyModeSwitch::write_state(bool state)
    {
      this->publish_state(state);
      if (this->parent_ != nullptr)
      {
        this->parent_->set_power_only_mode(state);
      }
    }

    void PlasmaSwitch::write_state(bool state)
    {
      this->publish_state(state);
      if (this->parent_ != nullptr)
      {
        this->parent_->set_plasma(state);
      }
    }

    static const uint8_t MIN_TEMPERATURE = 16;  // Minimum is 16°C for heat mode
    static const uint8_t MIN_TEMPERATURE_NON_HEAT = 18;  // 18°C minimum for cool/dry/fan/auto modes
    static const uint8_t MAX_TEMPERATURE = 30;  // Maximum is 30°C for all modes

    // Approximate LG pipe temperature mapping in °C.
    // This is consistent with the room-sensor mapping and gives realistic values.
    // Same formula as room temp: Temp(°C) = (192 - raw) / 3
    inline float lgap_raw_to_pipe_temp(uint8_t raw) {
      return float(192 - raw) / 3.0f;
    }

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

      // Build fan modes list - always include basic manual modes
      std::set<climate::ClimateFanMode> fan_modes = {
          climate::CLIMATE_FAN_LOW,
          climate::CLIMATE_FAN_MEDIUM,
          climate::CLIMATE_FAN_HIGH,
      };
      
      // Add optional fan modes if explicitly enabled
      if (this->supports_auto_fan_)
      {
        fan_modes.insert(climate::CLIMATE_FAN_AUTO);
      }
      if (this->supports_quiet_fan_)
      {
        fan_modes.insert(climate::CLIMATE_FAN_QUIET);  // SLOW mode
      }
      if (this->supports_turbo_fan_)
      {
        fan_modes.insert(climate::CLIMATE_FAN_FOCUS);  // TURBO/POWER mode
      }
      
      traits.set_supported_fan_modes(fan_modes);

      // Auto swing (auto airflow) - optional feature for ducted units
      // Only expose swing control if explicitly enabled in YAML
      if (this->supports_auto_swing_)
      {
        traits.set_supported_swing_modes({
            climate::CLIMATE_SWING_OFF,         // Manual airflow (displays as "Off" in HA)
            climate::CLIMATE_SWING_VERTICAL,    // Auto airflow (displays as "Vertical" in HA)
        });
      }
      // If not enabled, don't set swing modes at all - HA won't show swing control

      // Temperature limits per LG specification:
      // Heat mode: 16-30°C, all other modes: 18-30°C
      // ESPHome traits don't support mode-specific ranges, so we show 16-30°C
      // and enforce the 18°C minimum for non-heat modes in control()
      traits.set_visual_min_temperature(MIN_TEMPERATURE);
      traits.set_visual_max_temperature(MAX_TEMPERATURE);
      traits.set_visual_temperature_step(1);
      return traits;
    }

    void LGAPHVACClimate::control(const esphome::climate::ClimateCall &call)
    {
      ESP_LOGD(TAG, "esphome::climate::ClimateCall");

      // Check if power-only mode is active
      if (this->power_only_mode_)
      {
        // In power-only mode, only allow ON/OFF changes, block everything else
        if (call.get_mode().has_value())
        {
          climate::ClimateMode mode = *call.get_mode();
          // Only allow OFF mode change, block all other modes
          if (mode == climate::CLIMATE_MODE_OFF)
          {
            if (this->mode != mode)
            {
              this->power_state_ = 0;
              this->write_update_pending = true;
              this->mode = mode;
              this->publish_state();
            }
          }
          else
          {
            ESP_LOGW(TAG, "Mode change blocked - power-only mode is active");
          }
        }
        // Block all other control changes
        if (call.get_target_temperature().has_value() || call.get_fan_mode().has_value() || call.get_swing_mode().has_value())
        {
          ESP_LOGW(TAG, "Control changes blocked - power-only mode is active (only ON/OFF allowed)");
        }
        return;
      }

      // mode
      if (call.get_mode().has_value())
      {
        // Check if mode changes are locked
        if (this->lock_mode_ && this->mode != climate::CLIMATE_MODE_OFF)
        {
          ESP_LOGW(TAG, "Mode change blocked - mode lock is active");
          return;
        }
        
        ESP_LOGD(TAG, "Mode change requested");
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
          
          // Auto-start sleep timer if AC is turning ON and timer duration is set
          bool was_off = (this->mode == climate::CLIMATE_MODE_OFF);
          bool turning_on = (mode != climate::CLIMATE_MODE_OFF);
          if (was_off && turning_on && this->timer_duration_minutes_ > 0)
          {
            ESP_LOGI(TAG, "AC turning ON - auto-starting sleep timer for %.0f minutes", this->timer_duration_minutes_);
            this->start_timer(this->timer_duration_minutes_);
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
        // Check if fan speed changes are locked
        if (this->lock_fan_speed_)
        {
          ESP_LOGW(TAG, "Fan speed change blocked - fan speed lock is active");
          return;
        }
        
        ESP_LOGD(TAG, "Fan speed change requested");
        climate::ClimateFanMode fan_mode = *call.get_fan_mode();

        if (this->fan_mode != fan_mode)
        {
          // Fan speed encoding per LG protocol:
          // 0 = NO_CHANGE (don't use for setting)
          // 1 = LOW
          // 2 = MEDIUM
          // 3 = HIGH
          // 4 = AUTO
          // 5 = SLOW (QUIET)
          // 6 = POWER/TURBO
          // 7 = SLOW+POWER (rare)
          
          if (fan_mode == climate::CLIMATE_FAN_LOW)
          {
            this->fan_speed_ = 1;
          }
          else if (fan_mode == climate::CLIMATE_FAN_MEDIUM)
          {
            this->fan_speed_ = 2;
          }
          else if (fan_mode == climate::CLIMATE_FAN_HIGH)
          {
            this->fan_speed_ = 3;
          }
          else if (fan_mode == climate::CLIMATE_FAN_AUTO)
          {
            this->fan_speed_ = 4;
          }
          else if (fan_mode == climate::CLIMATE_FAN_QUIET)
          {
            this->fan_speed_ = 5;  // SLOW mode
          }
          else if (fan_mode == climate::CLIMATE_FAN_FOCUS)
          {
            this->fan_speed_ = 6;  // TURBO/POWER mode
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
        ESP_LOGD(TAG, "Swing mode change requested");
        climate::ClimateSwingMode swing_mode = *call.get_swing_mode();

        if (this->swing_mode != swing_mode)
        {
          // Auto Swing encoding (for ducted units: auto airflow mode)
          // 0 = OFF (manual airflow)
          // 1 = VERTICAL (automatic airflow pattern)
          // Note: Ducted IDUs have no physical vanes - this controls software airflow logic
          // CLIMATE_SWING_VERTICAL displays as "Vertical" in Home Assistant
          if (swing_mode == climate::CLIMATE_SWING_OFF)
          {
            this->swing_ = 0;
          }
          else if (swing_mode == climate::CLIMATE_SWING_VERTICAL)
          {
            if (!this->supports_auto_swing_)
            {
              ESP_LOGW(TAG, "Auto swing not supported on this zone - ignoring");
              return;
            }
            this->swing_ = 1;  // Auto airflow
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
        // Check if temperature changes are locked
        if (this->lock_temperature_)
        {
          ESP_LOGW(TAG, "Temperature change blocked - temperature lock is active");
          return;
        }
        
        // TODO: enable precision decimals as a yaml setting
        ESP_LOGD(TAG, "Temperature change requested");
        float temp = *call.get_target_temperature();
        
        // Apply mode-specific temperature limits
        // Heat mode: 16-30°C, all other modes: 18-30°C
        float min_temp = (this->mode == climate::CLIMATE_MODE_HEAT) ? MIN_TEMPERATURE : MIN_TEMPERATURE_NON_HEAT;
        float max_temp = MAX_TEMPERATURE;
        
        // Clamp temperature to valid range
        if (temp < min_temp)
        {
          ESP_LOGW(TAG, "Requested temperature %.1f°C is below minimum %.1f°C for current mode, clamping", temp, min_temp);
          temp = min_temp;
        }
        else if (temp > max_temp)
        {
          ESP_LOGW(TAG, "Requested temperature %.1f°C is above maximum %.1f°C, clamping", temp, max_temp);
          temp = max_temp;
        }
        
        if (temp != this->target_temperature_)
        {
          this->target_temperature_ = temp;
          this->target_temperature = temp;
        }

        this->write_update_pending = true;
        this->publish_state();
      }
    }

    void LGAPHVACClimate::handle_generate_lgap_request(std::vector<uint8_t> &message, uint8_t &request_id)
    {
      ESP_LOGV(TAG, "Generating %s request message for zone %d...", (this->write_update_pending ? "WRITE" : "READ"), this->zone_number);

      // only create a write request if there is a pending message
      int write_state = this->write_update_pending ? 2 : 0;

      // build payload in message buffer
      message.push_back(this->parent_->get_tx_byte_0());  // Byte 0 - configurable
      message.push_back(0);                                // Byte 1 - always 0
      message.push_back(request_id);                       // Byte 2 - request ID
      message.push_back(this->zone_number);                // Byte 3 - zone number
      
      // Byte 4: Control flags (TX4 in protocol)
      // bit0: ON (power state)
      // bit1: EXE (execute / write_state)
      // bit2: Lock (control lock)
      // bit3: reserved (0)
      // bit4: Plasma ion (air purification)
      uint8_t control_flags = this->power_state_ | write_state | (this->control_lock_ ? 0x04 : 0x00) | (this->plasma_ ? 0x10 : 0x00);
      message.push_back(control_flags);
      
      // Byte 5: Mode (bits 0-2) | Swing (bits 3-4) | Fan Speed (bits 4-6)
      // swing_ values: 0=OFF, 1=VERTICAL, 2=AUTO
      message.push_back(this->mode_ | (this->swing_ << 3) | (this->fan_speed_ << 4));
      message.push_back((uint8_t)(this->target_temperature_ - 15));

      // blank val for checksum then replace with calculation
      message.push_back(0);
      message[7] = this->parent_->calculate_checksum(message);
    }

    // todo: add handling for when mode change is requested but mode is already on with another zone, ie can't choose heat when cool is already on
    void LGAPHVACClimate::handle_on_message_received(std::vector<uint8_t> &message)
    {
      ESP_LOGD(TAG, "Processing climate message...");

      // handle bad class config
      if (this->zone_number < 0)
        return;
      if (message[4] != zone_number)
        return;

      bool publish_update = false;

      // process clean message as checksum already checked before reaching this point
      uint8_t power_state = (message[1] & 1);
      uint8_t mode = (message[6] & 7);
      
      // Control lock state (message[1] bit2 based on protocol TX4 layout)
      bool control_lock = (message[1] & 0x04) != 0;
      if (control_lock != this->control_lock_)
      {
        this->control_lock_ = control_lock;
        if (this->control_lock_switch_ != nullptr)
        {
          this->control_lock_switch_->publish_state(control_lock);
        }
        ESP_LOGD(TAG, "Control lock %s", control_lock ? "ENABLED" : "DISABLED");
      }

      // Plasma ion state (message[1] bit4 based on protocol TX4 layout)
      bool plasma = (message[1] & 0x10) != 0;
      if (plasma != this->plasma_)
      {
        this->plasma_ = plasma;
        if (this->plasma_switch_ != nullptr)
        {
          this->plasma_switch_->publish_state(plasma);
        }
        ESP_LOGD(TAG, "Plasma ion %s", plasma ? "ON" : "OFF");
      }

      // Error code (TX5 / message[5]) - 0 = OK, others = service codes
      uint8_t error_code = message[5];
      if (this->error_code_sensor_ != nullptr)
      {
        this->error_code_sensor_->publish_state(error_code);
      }
      
      if (error_code != 0)
      {
        ESP_LOGW(TAG, "Zone %d error code: %d", this->zone_number, error_code);
      }

      // Don't update control state from device while a write command is pending
      // This prevents the device's old state from overwriting the user's new command
      // But we still want to update measurement data (temp, load byte) below
      if (!this->write_update_pending)
      {
        // power state and mode
        // home assistant climate treats them as a single entity
        // this logic combines them from lgap into a single entity
        if (power_state != this->power_state_ || mode != this->mode_)
        {
          // handle mode
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

          // handle power state
          if (power_state == 0)
          {
            this->mode = climate::CLIMATE_MODE_OFF;
          }

          // Check if mode changes should be enforced (mode lock or power-only mode)
          if ((this->lock_mode_ || this->power_only_mode_) && mode != this->mode_ && this->power_state_ == 1)
          {
            ESP_LOGW(TAG, "Mode changed at wall controller while lock active - reverting to previous mode");
            this->write_update_pending = true;  // Force write to revert
            // Don't update mode_ to keep previous value
          }
          else
          {
            // update state
            publish_update = true;
            this->mode_ = mode;
            this->power_state_ = power_state;
          }
        }

        // Auto Swing (message[6] bit 3) - for ducted units: auto airflow mode
        // 0 = OFF (manual airflow)
        // 1 = VERTICAL (automatic airflow pattern)
        // Note: Ducted IDUs have no physical vanes - this is software airflow control
        // CLIMATE_SWING_VERTICAL displays as "Vertical" in Home Assistant
        uint8_t swing = (message[6] >> 3) & 1;
        if (swing != this->swing_)
        {
          if (swing == 0)
          {
            this->swing_mode = climate::CLIMATE_SWING_OFF;
          }
          else if (swing == 1)
          {
            this->swing_mode = climate::CLIMATE_SWING_VERTICAL;  // Displays as "Vertical" in HA
          }
          else
          {
            ESP_LOGE(TAG, "Invalid swing received: %d", swing);
          }

          // update state
          this->swing_ = swing;
          publish_update = true;
        }

        // fan speed
        // Fan speed decoding per LG protocol:
        // 0 = NO_CHANGE / model-dependent (treat as no update)
        // 1 = LOW
        // 2 = MEDIUM
        // 3 = HIGH
        // 4 = AUTO
        // 5 = SLOW (QUIET)
        // 6 = POWER/TURBO
        // 7 = SLOW+POWER (rare)
        uint8_t fan_speed = ((message[6] >> 4) & 7);
        if (fan_speed != this->fan_speed_ && fan_speed != 0)  // 0 = NO_CHANGE
        {
          if (fan_speed == 1)
          {
            this->fan_mode = climate::CLIMATE_FAN_LOW;
          }
          else if (fan_speed == 2)
          {
            this->fan_mode = climate::CLIMATE_FAN_MEDIUM;
          }
          else if (fan_speed == 3)
          {
            this->fan_mode = climate::CLIMATE_FAN_HIGH;
          }
          else if (fan_speed == 4)
          {
            this->fan_mode = climate::CLIMATE_FAN_AUTO;
          }
          else if (fan_speed == 5)
          {
            this->fan_mode = climate::CLIMATE_FAN_QUIET;  // SLOW mode
          }
          else if (fan_speed == 6)
          {
            this->fan_mode = climate::CLIMATE_FAN_FOCUS;  // TURBO/POWER mode
          }
          else if (fan_speed == 7)
          {
            // SLOW+POWER mode - map to FOCUS for now
            this->fan_mode = climate::CLIMATE_FAN_FOCUS;
            ESP_LOGW(TAG, "Received SLOW+POWER fan mode (7), mapping to TURBO");
          }
          else
          {
            ESP_LOGE(TAG, "Invalid fan speed received: %d", fan_speed);
          }

          // Check if fan speed changes should be enforced (fan speed lock or power-only mode)
          if ((this->lock_fan_speed_ || this->power_only_mode_) && fan_speed != this->fan_speed_)
          {
            ESP_LOGW(TAG, "Fan speed changed at wall controller while lock active - reverting to previous speed");
            this->write_update_pending = true;  // Force write to revert
            // Don't update fan_speed_ to keep previous value
          }
          else
          {
            // update state
            this->fan_speed_ = fan_speed;
            publish_update = true;
          }
        }

        // Target temperature in °C from LGAP frame
        // Lower nibble of message[7] holds the integer offset (0 => 15°C, 1 => 16°C, etc.)
        // This matches the LgController pattern: (buffer[6] & 0xF) + 15
        // Note: LGAP protocol may not support half-degree increments like the single-head controller
        uint8_t raw_target = message[7] & 0x0F;
        float target_temperature = static_cast<float>(raw_target + 15);
        
        // If LGAP protocol supports half-degree flag (similar to single-head), add here:
        // if (message[X] & 0x1) target_temperature += 0.5f;
        
        if (target_temperature != this->target_temperature_)
        {
          // Check if temperature changes should be enforced (temperature lock or power-only mode)
          if (this->lock_temperature_ || this->power_only_mode_)
          {
            ESP_LOGW(TAG, "Temperature changed at wall controller (%.0f°C→%.0f°C) while lock active - reverting", 
                     this->target_temperature_, target_temperature);
            this->write_update_pending = true;  // Force write to revert
            // Don't update target_temperature_ to keep previous value
          }
          else
          {
            this->target_temperature_ = target_temperature;
            this->target_temperature = target_temperature;
            publish_update = true;
          }
        }
      } // end of control state update block (write_update_pending check)

      // current temp - always update measurement data
      // TODO: implement precision setting for reported temperature
      // OLD (wrong, uses only low nibble):
      // int current_temperature = (message[8] & 0xf) + 15;
      // NEW (from LG table: ~3 counts per °C, offset 192):
      // Temp(°C) = floor((192 - raw_byte) / 3)
      uint8_t raw = message[8];
      int current_temperature = (192 - raw) / 3;  // integer division floors automatically
      ESP_LOGD(TAG, "Current temperature: %d", current_temperature);
      // checks that temperature is different AND that the publish time interval has passed
      if (current_temperature != this->current_temperature_)
      {
        // Publish immediately on first reading (temperature_last_publish_time_ == 0)
        // or after the configured time interval has elapsed
        bool is_first_reading = (this->temperature_last_publish_time_ == 0);
        bool interval_elapsed = (this->temperature_last_publish_time_ + this->temperature_publish_time_ <= millis());
        
        if (is_first_reading || interval_elapsed)
        {
          ESP_LOGD(TAG, "Temperature update - %s. Sending update...", 
                   is_first_reading ? "first reading" : "time interval elapsed");
          this->temperature_last_publish_time_ = millis();
          this->current_temperature_ = current_temperature;
          this->current_temperature = current_temperature;
          publish_update = true;
        } else {
          ESP_LOGD(TAG, "Temperature update time hasn't lapsed. Ignoring temperature difference...");
        }
      }

      // Extract and decode pipe temperatures (message[9] = Pipe-In, message[10] = Pipe-Out)
      // Using the same LG temperature mapping as room temp: Temp(°C) = (192 - raw) / 3
      // These represent the refrigerant line temperatures for this zone
      uint8_t raw_pipe_in = message[9];
      uint8_t raw_pipe_out = message[10];
      
      float pipe_in_temp_c = lgap_raw_to_pipe_temp(raw_pipe_in);
      float pipe_out_temp_c = lgap_raw_to_pipe_temp(raw_pipe_out);
      
      // Publish pipe-in temperature sensor if configured
      if (this->pipe_in_sensor_ != nullptr)
      {
        this->pipe_in_sensor_->publish_state(pipe_in_temp_c);
      }
      
      // Publish pipe-out temperature sensor if configured
      if (this->pipe_out_sensor_ != nullptr)
      {
        this->pipe_out_sensor_->publish_state(pipe_out_temp_c);
      }
      
      ESP_LOGD(TAG, "Pipe temps - In: %.1f°C (raw: %d), Out: %.1f°C (raw: %d)", 
               pipe_in_temp_c, raw_pipe_in, pipe_out_temp_c, raw_pipe_out);

      // LG LGAP Protocol - LonWorks-aligned load management bytes
      // These bytes match LG's PI485→LonWorks gateway mappings used in commercial BMS
      // 
      // Message structure (16 bytes):
      //   0: 0x10 (frame marker)
      //   1: power state + flags
      //   2: request ID
      //   3: (reserved/unknown)
      //   4: zone number
      //   5: (reserved/unknown)
      //   6: mode + swing + fan
      //   7: target temp
      //   8: room temp
      //   9: pipe-in temp
      //   10: pipe-out temp
      //   11: Zone Active Load (LonWorks: nvoLoadEstimate/nvoUnitLoad)
      //   12: Zone Power State (LonWorks: nvoOnOff) - 0=ON, 1=OFF
      //   13: Zone Design Load (LonWorks: nciRatedCapacity) - fixed design weight
      //   14: ODU Total Load (LonWorks: nvoThermalLoad) - compressor load
      //   15: checksum
      
      // Byte 11: Zone Active Load (LonWorks: nvoLoadEstimate / nvoUnitLoad)
      // Dynamic real-time per-zone thermal load estimate (0-255)
      // - Typical idle: ~204
      // - Under load: 80-220 range
      // - LOWER value = HIGHER active IDU load (inverse relationship!)
      // - Rises when zone is calling for cooling/heating
      // - Falls as zone approaches setpoint
      // - Proportional to design load but affected by temp delta & demand
      uint8_t zone_active_load = message[11];
      if (this->zone_active_load_sensor_ != nullptr)
      {
        this->zone_active_load_sensor_->publish_state(zone_active_load);
      }
      
      // Byte 12: Zone Power State Flag (LonWorks: nvoOnOff)
      // Simple ON/OFF state with IDU-level granularity (0-1)
      // - 0 = RUNNING / ON
      // - 1 = OFF / IDLE
      // - May jitter during state transitions (ON→OFF→ON) as different boards report at different times
      // - Multiple indoor sub-zones may share the same IDU-level ON/OFF state
      uint8_t zone_power_state = message[12];
      if (this->zone_power_state_sensor_ != nullptr)
      {
        this->zone_power_state_sensor_->publish_state(zone_power_state);
      }
      
      // Byte 13: Zone Design Load Index (LonWorks: nciRatedCapacity)
      // Fixed design load weight representing the rated capacity of this IDU
      // - Does NOT change with on/off state
      // - Proportional to duct size / airflow potential / nominal cooling capacity
      // - Used by BMS to model expected capacity split among zones
      // Example values: Small rooms: 9, Medium: 12, Large: 24
      uint8_t zone_design_load = message[13];
      if (this->zone_design_load_sensor_ != nullptr)
      {
        this->zone_design_load_sensor_->publish_state(zone_design_load);
      }
      
      // Byte 14: ODU Total Load Index (LonWorks: nvoThermalLoad / nvoOduLoadFactor)
      // ODU-level compressor load estimate (0-255)
      // - Same value reported to all IDUs connected to the same ODU
      // - Approximately sum of design indices (byte 13) of all ON zones, smoothed
      // - Increases with number of active zones
      // - Max load = sum of rated loads of connected zones
      // - Goes to 0 when all zones are off
      // Use (byte14 / sum_of_all_design_loads) to calculate ODU load percentage
      // Example: All 5 downstairs zones total 78 (9+9+12+24+24), if byte14=36 → ODU at 46% load
      uint8_t odu_total_load = message[14];
      if (this->odu_total_load_sensor_ != nullptr)
      {
        this->odu_total_load_sensor_->publish_state(odu_total_load);
      }
      
      ESP_LOGD(TAG, "LonWorks Load - Active: %d, Power: %d, Design: %d, ODU: %d", 
               zone_active_load, zone_power_state, zone_design_load, odu_total_load);

      // send update to home assistant with all the changed variables
      if (publish_update == true)
      {
        this->publish_state();
      }
    }

    void LGAPHVACClimate::start_timer(float duration_minutes)
    {
      if (duration_minutes <= 0)
      {
        ESP_LOGW(TAG, "Cannot start timer - duration must be > 0 minutes");
        this->cancel_timer();
        return;
      }

      uint32_t duration_ms = static_cast<uint32_t>(duration_minutes * 60 * 1000);
      this->timer_end_time_ = millis() + duration_ms;
      this->timer_active_ = true;
      this->timer_last_update_ = millis();

      ESP_LOGI(TAG, "Sleep timer set for %.0f minutes", duration_minutes);
      
      // Publish initial remaining time
      if (this->timer_remaining_sensor_ != nullptr)
      {
        this->timer_remaining_sensor_->publish_state(duration_minutes);
      }
    }

    void LGAPHVACClimate::cancel_timer()
    {
      if (this->timer_active_)
      {
        this->timer_active_ = false;
        ESP_LOGI(TAG, "Sleep timer cancelled");
        
        // Publish 0 remaining time
        if (this->timer_remaining_sensor_ != nullptr)
        {
          this->timer_remaining_sensor_->publish_state(0);
        }
      }
    }

    void LGAPHVACClimate::loop()
    {
      if (!this->timer_active_)
        return;

      uint32_t now = millis();
      
      // Check if timer has expired
      if (now >= this->timer_end_time_)
      {
        ESP_LOGI(TAG, "Sleep timer expired - turning unit OFF (duration %.0f min remains saved)", this->timer_duration_minutes_);
        this->timer_active_ = false;
        
        // Turn off the unit
        auto call = this->make_call();
        call.set_mode(climate::CLIMATE_MODE_OFF);
        call.perform();
        
        // Duration stays saved (timer_duration_minutes_) - will auto-restart next time AC turns ON
        // Don't reset timer_duration_number_ to 0 - user's setting is preserved
        
        // Publish 0 remaining time
        if (this->timer_remaining_sensor_ != nullptr)
        {
          this->timer_remaining_sensor_->publish_state(0);
        }
        return;
      }

      // Update remaining time every 10 seconds
      if (now - this->timer_last_update_ >= 10000)
      {
        this->timer_last_update_ = now;
        
        uint32_t remaining_ms = this->timer_end_time_ - now;
        float remaining_minutes = remaining_ms / 60000.0f;
        
        if (this->timer_remaining_sensor_ != nullptr)
        {
          this->timer_remaining_sensor_->publish_state(remaining_minutes);
        }
        
        ESP_LOGV(TAG, "Sleep timer remaining: %.1f minutes", remaining_minutes);
      }
    }

    void LGAPHVACClimate::set_control_lock(bool state)
    {
      if (this->control_lock_ != state)
      {
        this->control_lock_ = state;
        this->write_update_pending = true;
        ESP_LOGI(TAG, "Control lock %s", state ? "ENABLED" : "DISABLED");
      }
    }

    void LGAPHVACClimate::set_lock_temperature(bool state)
    {
      if (this->lock_temperature_ != state)
      {
        this->lock_temperature_ = state;
        ESP_LOGI(TAG, "Temperature lock %s", state ? "ENABLED" : "DISABLED");
      }
    }

    void LGAPHVACClimate::set_lock_fan_speed(bool state)
    {
      if (this->lock_fan_speed_ != state)
      {
        this->lock_fan_speed_ = state;
        ESP_LOGI(TAG, "Fan speed lock %s", state ? "ENABLED" : "DISABLED");
      }
    }

    void LGAPHVACClimate::set_lock_mode(bool state)
    {
      if (this->lock_mode_ != state)
      {
        this->lock_mode_ = state;
        ESP_LOGI(TAG, "Mode lock %s", state ? "ENABLED" : "DISABLED");
      }
    }

    void LGAPHVACClimate::set_power_only_mode(bool state)
    {
      if (this->power_only_mode_ != state)
      {
        this->power_only_mode_ = state;
        ESP_LOGI(TAG, "Power-only mode %s", state ? "ENABLED (only ON/OFF allowed)" : "DISABLED");
      }
    }

    void LGAPHVACClimate::set_plasma(bool state)
    {
      if (this->plasma_ != state)
      {
        this->plasma_ = state;
        this->write_update_pending = true;
        ESP_LOGI(TAG, "Plasma ion %s", state ? "ON" : "OFF");
      }
    }

  } // namespace lgap
} // namespace esphome