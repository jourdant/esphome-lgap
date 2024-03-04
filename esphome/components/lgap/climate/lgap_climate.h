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
        unsigned char power_state_{0};
        unsigned char swing_{0};
        unsigned char mode_{0};
        unsigned char fan_speed_{0};

        float current_temperature_{0.0f};
        float target_temperature_{0.0f};

        void handle_on_message_received(std::vector<unsigned char> &message) override;
        void handle_generate_lgap_request(std::vector<unsigned char> &message) override;
      };

  } // namespace lgap
} // namespace esphome