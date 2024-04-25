#pragma once
#include <vector>
#include <stdint.h>
#include "lgap.h"

namespace esphome
{
  namespace lgap
  {
    class LGAP;

    class LGAPDevice : public Component
    {
      public:
        // float get_setup_priority() const override;
        bool write_update_pending{false};
        
        void set_parent(LGAP *parent) { parent_ = parent; }
        void set_zone_number(int zone_number) { this->zone_number = zone_number; }

        void on_message_received(std::vector<uint8_t> &message);
        void generate_lgap_request(std::vector<uint8_t> &message);
        
        // uint32_t last_uart_update_time_{0};
        // uint32_t last_ha_update_time_{0};

      protected:
        friend LGAP;
        LGAP *parent_;

        int zone_number{-1};

        virtual void handle_on_message_received(std::vector<uint8_t> &message) = 0;
        virtual void handle_generate_lgap_request(std::vector<uint8_t> &message) = 0;
    };

  } // namespace lgap
} // namespace esphome