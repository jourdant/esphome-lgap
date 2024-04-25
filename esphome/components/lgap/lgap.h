#pragma once

#include "esphome/core/component.h"
#include "esphome/components/uart/uart.h"
#include <vector>
#include "lgap_device.h"

namespace esphome
{
  namespace lgap
  {
    class LGAPDevice; 
    
    class LGAP : public uart::UARTDevice, public Component
    {
      public:
        uint8_t calculate_checksum(const std::vector<uint8_t> &data);
        const char *const TAG = "lgap";

        // load this class after the UART is instantiated
        float get_setup_priority() const override;
        void dump_config() override;
        void loop() override;
        
        void set_debug_wait_time(uint16_t time_in_ms) { this->debug_wait_time_= time_in_ms; }
        void set_debug(bool debug) { this->debug_ = debug; }

        void set_flow_control_pin(GPIOPin *flow_control_pin) { this->flow_control_pin_ = flow_control_pin; }
        void set_send_wait_time(uint16_t time_in_ms) { this->send_wait_time_ = time_in_ms; }
        void set_receive_wait_time(uint16_t time_in_ms) { this->receive_wait_time_ = time_in_ms; }
        void set_zone_check_wait_time(uint16_t time_in_ms) { this->zone_check_wait_time_ = time_in_ms; }
        void register_device(LGAPDevice *device) {
          ESP_LOGV(TAG, "Registering device");
          this->devices_.push_back(device);
        }

      protected:
        GPIOPin *flow_control_pin_{nullptr};

        // state_: 0 - waiting for a message to be sent
        // state_: 1 - waiting for a response to a sent message
        // state_: 2 - reading a valid response
        int state_{0};
        bool debug_{true};
        int last_zone_checked_index_{-1};

        //used for keeping track of req/resp pairs
        uint8_t last_request_id{0};
        uint8_t last_request_zone{0};

        uint16_t debug_wait_time_{1000};
        uint16_t zone_check_wait_time_{1000};
        uint16_t send_wait_time_{250};
        uint16_t receive_wait_time_{250};

        uint32_t last_debug_time_{0};
        uint32_t last_zone_check_time_{0};
        uint32_t last_send_time_{0};
        uint32_t last_receive_time_{0};

        std::vector<uint8_t> rx_buffer_;
        std::vector<uint8_t> tx_buffer_;

        std::vector<LGAPDevice *> devices_{};

    };

  } // namespace lgap
} // namespace esphome