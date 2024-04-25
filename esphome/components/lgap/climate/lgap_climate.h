#include "../lgap.h"
#include "../lgap_device.h"

#include "esphome/components/climate/climate.h"

namespace esphome
{
  namespace lgap
  {
    class LGAPHVACClimate : public LGAPDevice, public climate::Climate
    {
      public:
        void dump_config() override;       
        void setup() override;
        virtual esphome::climate::ClimateTraits traits() override;
        virtual void control(const esphome::climate::ClimateCall &call) override;

      protected:
        uint8_t power_state_{0};
        uint8_t swing_{0};
        uint8_t mode_{0};
        uint8_t fan_speed_{0};

        float current_temperature_{0.0f};
        float target_temperature_{0.0f};

        //todo: evaluate whether to use esppreferenceobject or not
        // ESPPreferenceObject power_state_preference_; //uint8_t
        // ESPPreferenceObject swing_preference_; //uint8_t
        // ESPPreferenceObject mode_preference_; //uint8_t
        // ESPPreferenceObject fan_speed_preference_; //uint8_t

        // optional<float> target_temperature_;
        // optional<float> current_temperature_;

        void handle_on_message_received(std::vector<uint8_t> &message) override;
        void handle_generate_lgap_request(std::vector<uint8_t> &message) override;
      };

  } // namespace lgap
} // namespace esphome