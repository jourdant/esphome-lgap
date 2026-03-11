#pragma once

#include "esphome/core/component.h"
#include "esphome/components/uart/uart.h"
#include "esphome/components/sensor/sensor.h"
#include <vector>
#include "lgap_device.h"

namespace esphome
{
  namespace lgap
  {
    class LGAPDevice;

    enum State
    {
      REQUEST_NEXT_DEVICE_STATUS,
      PROCESS_DEVICE_STATUS_START,
      PROCESS_DEVICE_STATUS_CONTINUE
    };

    class LGAP : public uart::UARTDevice, public Component
    {
      public:
        uint8_t calculate_checksum(const std::vector<uint8_t> &data);
        const char *const TAG = "lgap";

        // load this class after the UART is instantiated
        float get_setup_priority() const override;
        void dump_config() override;
        void loop() override;

        void set_loop_wait_time(uint16_t time_in_ms) { this->loop_wait_time_ = time_in_ms; }
        void set_debug(bool debug) { this->debug_ = debug; }

        void set_flow_control_pin(GPIOPin *flow_control_pin) { this->flow_control_pin_ = flow_control_pin; }
        void set_receive_wait_time(uint16_t time_in_ms) { this->receive_wait_time_ = time_in_ms; }
        void set_tx_byte_0(uint8_t byte) { this->tx_byte_0_ = byte; }
        uint8_t get_tx_byte_0() const { return this->tx_byte_0_; }
        
        void register_device(LGAPDevice *device)
        {
          ESP_LOGD(TAG, "Registering device");
          this->devices_.push_back(device);
        }

      protected:
        void clear_rx_buffer();

        GPIOPin *flow_control_pin_{nullptr};

        State state_{REQUEST_NEXT_DEVICE_STATUS};
        bool debug_{true};
        int last_zone_checked_index_{-1};

        uint16_t loop_wait_time_{500};
        uint16_t receive_wait_time_{500};
        uint8_t tx_byte_0_{0x80};

        // used for keeping track of req/resp pairs
        uint8_t last_request_id_{250};
        uint8_t last_request_zone_{0};

        // timestamps
        uint32_t last_loop_time_{0};
        uint32_t last_zone_check_time_{0};
        uint32_t receive_until_time_{0};

        std::vector<uint8_t> rx_buffer_;
        std::vector<uint8_t> tx_buffer_;

        std::vector<LGAPDevice *> devices_{};

    };
  } // namespace lgap
} // namespace esphome