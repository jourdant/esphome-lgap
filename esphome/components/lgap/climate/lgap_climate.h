#include "../lgap.h"
#include "../lgap_device.h"

#include "esphome/components/climate/climate.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/number/number.h"
#include "esphome/components/button/button.h"
#include "esphome/components/switch/switch.h"

namespace esphome
{
  namespace lgap
  {
    class LGAPHVACClimate;

    // Timer duration number with automatic start/cancel
    class TimerDurationNumber : public number::Number
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void control(float value) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    // Control lock switch (child lock)
    class ControlLockSwitch : public switch_::Switch
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void write_state(bool state) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    // Lock temperature changes switch
    class LockTemperatureSwitch : public switch_::Switch
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void write_state(bool state) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    // Lock fan speed changes switch
    class LockFanSpeedSwitch : public switch_::Switch
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void write_state(bool state) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    // Lock mode changes switch
    class LockModeSwitch : public switch_::Switch
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void write_state(bool state) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    // Power only mode switch (allow only ON/OFF, lock all other controls)
    class PowerOnlyModeSwitch : public switch_::Switch
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void write_state(bool state) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    // Plasma ion switch (air purification feature)
    class PlasmaSwitch : public switch_::Switch
    {
      public:
        void set_parent(LGAPHVACClimate *parent) { this->parent_ = parent; }
        void write_state(bool state) override;
      protected:
        LGAPHVACClimate *parent_{nullptr};
    };

    class LGAPHVACClimate : public LGAPDevice, public climate::Climate
    {
      public:
        void dump_config() override;       
        void setup() override;
        void set_temperature_publish_time(int temperature_publish_time) { this->temperature_publish_time_ = temperature_publish_time; }
        void set_supports_auto_swing(bool supports) { this->supports_auto_swing_ = supports; }
        void set_supports_auto_fan(bool supports) { this->supports_auto_fan_ = supports; }
        void set_supports_quiet_fan(bool supports) { this->supports_quiet_fan_ = supports; }
        void set_supports_turbo_fan(bool supports) { this->supports_turbo_fan_ = supports; }
        void set_supports_plasma(bool supports) { this->supports_plasma_ = supports; }
        void set_pipe_in_sensor(sensor::Sensor *sensor) { this->pipe_in_sensor_ = sensor; }
        void set_pipe_out_sensor(sensor::Sensor *sensor) { this->pipe_out_sensor_ = sensor; }
        void set_error_code_sensor(sensor::Sensor *sensor) { this->error_code_sensor_ = sensor; }
        
        // Timer control
        void set_timer_duration_number(TimerDurationNumber *number) { 
          this->timer_duration_number_ = number; 
          number->set_parent(this);
        }
        void set_timer_remaining_sensor(sensor::Sensor *sensor) { this->timer_remaining_sensor_ = sensor; }
        void start_timer(float minutes);
        void cancel_timer();
        void loop() override;
        
        // Control lock
        void set_control_lock_switch(ControlLockSwitch *switch_) {
          this->control_lock_switch_ = switch_;
          switch_->set_parent(this);
        }
        void set_control_lock(bool state);
        bool get_control_lock() const { return this->control_lock_; }
        
        // Function restrictions (partial locks)
        void set_lock_temperature_switch(LockTemperatureSwitch *switch_) {
          this->lock_temperature_switch_ = switch_;
          switch_->set_parent(this);
        }
        void set_lock_fan_speed_switch(LockFanSpeedSwitch *switch_) {
          this->lock_fan_speed_switch_ = switch_;
          switch_->set_parent(this);
        }
        void set_lock_mode_switch(LockModeSwitch *switch_) {
          this->lock_mode_switch_ = switch_;
          switch_->set_parent(this);
        }
        void set_power_only_mode_switch(PowerOnlyModeSwitch *switch_) {
          this->power_only_mode_switch_ = switch_;
          switch_->set_parent(this);
        }
        void set_plasma_switch(PlasmaSwitch *switch_) {
          this->plasma_switch_ = switch_;
          switch_->set_parent(this);
        }
        
        void set_lock_temperature(bool state);
        void set_lock_fan_speed(bool state);
        void set_lock_mode(bool state);
        void set_power_only_mode(bool state);
        void set_plasma(bool state);
        bool get_plasma() const { return this->plasma_; }
        void set_zone_active_load_sensor(sensor::Sensor *sensor) { this->zone_active_load_sensor_ = sensor; }
        void set_zone_power_state_sensor(sensor::Sensor *sensor) { this->zone_power_state_sensor_ = sensor; }
        void set_zone_design_load_sensor(sensor::Sensor *sensor) { this->zone_design_load_sensor_ = sensor; }
        void set_odu_total_load_sensor(sensor::Sensor *sensor) { this->odu_total_load_sensor_ = sensor; }
        virtual esphome::climate::ClimateTraits traits() override;
        virtual void control(const esphome::climate::ClimateCall &call) override;
        


      protected:
        uint32_t temperature_publish_time_{300000};
        uint32_t temperature_last_publish_time_{0};
        
        bool supports_auto_swing_{false};  // Whether to expose auto swing mode
        bool supports_auto_fan_{false};    // Whether to expose auto fan speed mode
        bool supports_quiet_fan_{false};   // Whether to expose quiet/slow fan mode
        bool supports_turbo_fan_{false};   // Whether to expose turbo/power fan mode
        bool supports_plasma_{false};      // Whether to expose plasma ion control

        uint8_t power_state_{0};
        uint8_t swing_{0};
        uint8_t mode_{0};
        uint8_t fan_speed_{0};
        bool control_lock_{false};  // Child lock state (TX4 bit2)
        bool plasma_{false};        // Plasma ion state (TX4 bit4)
        
        // Function restrictions (partial locks)
        bool lock_temperature_{false};  // Lock temperature up/down
        bool lock_fan_speed_{false};    // Lock fan speed changes
        bool lock_mode_{false};         // Lock mode changes
        bool power_only_mode_{false};   // Only allow ON/OFF, lock all other controls

        float current_temperature_{0.0f};
        float target_temperature_{0.0f};
        
        // Timer state
        bool timer_active_{false};
        uint32_t timer_end_time_{0};  // millis() when timer expires
        uint32_t timer_last_update_{0};  // Last time we published remaining time
        
        sensor::Sensor *pipe_in_sensor_{nullptr};
        sensor::Sensor *pipe_out_sensor_{nullptr};
        sensor::Sensor *error_code_sensor_{nullptr};            // Byte 5 - Error code (0=OK, others=service codes)
        sensor::Sensor *zone_active_load_sensor_{nullptr};      // Byte 11 - LonWorks nvoLoadEstimate
        sensor::Sensor *zone_power_state_sensor_{nullptr};      // Byte 12 - LonWorks nvoOnOff
        sensor::Sensor *zone_design_load_sensor_{nullptr};      // Byte 13 - LonWorks nciRatedCapacity
        sensor::Sensor *odu_total_load_sensor_{nullptr};        // Byte 14 - LonWorks nvoThermalLoad
        
        // Timer components
        TimerDurationNumber *timer_duration_number_{nullptr};
        sensor::Sensor *timer_remaining_sensor_{nullptr};
        
        // Control lock switch
        ControlLockSwitch *control_lock_switch_{nullptr};
        
        // Function restriction switches
        LockTemperatureSwitch *lock_temperature_switch_{nullptr};
        LockFanSpeedSwitch *lock_fan_speed_switch_{nullptr};
        LockModeSwitch *lock_mode_switch_{nullptr};
        PowerOnlyModeSwitch *power_only_mode_switch_{nullptr};
        PlasmaSwitch *plasma_switch_{nullptr};

        //todo: evaluate whether to use esppreferenceobject or not
        // ESPPreferenceObject power_state_preference_; //uint8_t
        // ESPPreferenceObject swing_preference_; //uint8_t
        // ESPPreferenceObject mode_preference_; //uint8_t
        // ESPPreferenceObject fan_speed_preference_; //uint8_t

        // optional<float> target_temperature_;
        // optional<float> current_temperature_;

        void handle_on_message_received(std::vector<uint8_t> &message) override;
        void handle_generate_lgap_request(std::vector<uint8_t> &message, uint8_t &request_id) override;
      };

  } // namespace lgap
} // namespace esphome