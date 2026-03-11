#include "../lgap.h"
#include "../lgap_device.h"

#include "esphome/components/climate/climate.h"
#include "esphome/components/sensor/sensor.h"

namespace esphome
{
  namespace lgap
  {
    class LGAPHVACClimate : public LGAPDevice, public climate::Climate
    {
      public:
        void dump_config() override;       
        void setup() override;
        void set_temperature_publish_time(int temperature_publish_time) { this->temperature_publish_time_ = temperature_publish_time; }
        void set_power_sensor(sensor::Sensor *sensor) { this->power_sensor_ = sensor; }
        void set_load_byte_sensor(sensor::Sensor *sensor) { this->load_byte_sensor_ = sensor; }
        void set_pipe_in_sensor(sensor::Sensor *sensor) { this->pipe_in_sensor_ = sensor; }
        void set_pipe_out_sensor(sensor::Sensor *sensor) { this->pipe_out_sensor_ = sensor; }
        virtual esphome::climate::ClimateTraits traits() override;
        virtual void control(const esphome::climate::ClimateCall &call) override;
        
        // Public accessors for power calculation
        uint8_t get_load_byte() const { return this->load_byte_; }
        bool is_unit_on() const { return this->power_state_ == 1; }
        sensor::Sensor *get_power_sensor() const { return this->power_sensor_; }


      protected:
        uint32_t temperature_publish_time_{300000};
        uint32_t temperature_last_publish_time_{0};

        uint8_t power_state_{0};
        uint8_t swing_{0};
        uint8_t mode_{0};
        uint8_t fan_speed_{0};
        uint8_t load_byte_{0};  // Byte 10 from response - load/operation rate

        float current_temperature_{0.0f};
        float target_temperature_{0.0f};
        
        sensor::Sensor *power_sensor_{nullptr};
        sensor::Sensor *load_byte_sensor_{nullptr};
        sensor::Sensor *pipe_in_sensor_{nullptr};
        sensor::Sensor *pipe_out_sensor_{nullptr};

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