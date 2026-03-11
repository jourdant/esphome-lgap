#include "lgap.h"
#include "lgap_device.h"
#include "climate/lgap_climate.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include <cinttypes>
#include <vector>

namespace esphome
{
  namespace lgap
  {
    float LGAP::get_setup_priority() const { return setup_priority::DATA; }

    void LGAP::dump_config()
    {
      ESP_LOGCONFIG(TAG, "LGAP:");
      check_uart_settings(4800);

      ESP_LOGCONFIG(TAG, "  Flow Control Pin:");
      if (this->flow_control_pin_ != nullptr)
      {
        this->flow_control_pin_->dump_summary();
      }
      else
      {
        ESP_LOGCONFIG(TAG, "Flow control pin not set.");
      }

      ESP_LOGCONFIG(TAG, "  Loop wait time: %dms", this->loop_wait_time_);
      ESP_LOGCONFIG(TAG, "  Receive wait time: %dms", this->receive_wait_time_);
      ESP_LOGCONFIG(TAG, "  TX Byte 0: 0x%02X", this->tx_byte_0_);
      ESP_LOGCONFIG(TAG, "  Child devices: %d", this->devices_.size());
      if (this->debug_ == true)
      {
        ESP_LOGCONFIG(TAG, "  Debug: true");
      }
    }

    // the checksum method is the same as the LG wall controller
    // borrowed this checksum function from:
    // https://github.com/JanM321/esphome-lg-controller/blob/998b78a212f798267feca0a91475726516228b56/esphome/lg-controller.h#L631C1-L637C6
    uint8_t LGAP::calculate_checksum(const std::vector<uint8_t> &data)
    {
      size_t result = 0;
      for (size_t i = 0; i < data.size() - 1; i++)
      {
        result += data[i];
      }
      return (result & 0xff) ^ 0x55;
    }

    void LGAP::clear_rx_buffer()
    {
      ESP_LOGV(TAG, "Clearing rx buffer...");

      // clear internal rx buffer
      this->rx_buffer_.clear();
      // clear uart rx buffer
      while (this->available())
        this->read();
    }

    void LGAP::loop()
    {
      // do nothing if there are no LGAP devices registered
      if (this->devices_.size() == 0)
        return;

      if (this->state_ == State::REQUEST_NEXT_DEVICE_STATUS)
      {
        // enable wait time between loops
        if ((millis() - this->last_loop_time_) < this->loop_wait_time_)
          return;
        else
          this->last_loop_time_ = millis();

        ESP_LOGV(TAG, "REQUEST_NEXT_DEVICE_STATUS");

        // cycle through zones
        this->last_zone_checked_index_ = (this->last_zone_checked_index_ + 1) > this->devices_.size() - 1 ? 0 : this->last_zone_checked_index_ + 1;
        ESP_LOGV(TAG, "devices_[%d]->zone_number = %d", this->last_zone_checked_index_, this->devices_[this->last_zone_checked_index_]->zone_number);

        // retrieve lgap message from device if it has a valid zone number
        if (this->devices_[this->last_zone_checked_index_]->zone_number > -1)
        {
          ESP_LOGV(TAG, "Requesting update from zone %d", this->devices_[this->last_zone_checked_index_]->zone_number);

          this->tx_buffer_.clear();
          this->devices_[this->last_zone_checked_index_]->generate_lgap_request(this->tx_buffer_, this->last_request_id_);

          // signal flow control write mode enabled
          if (this->flow_control_pin_ != nullptr)
            this->flow_control_pin_->digital_write(true);

          // send data over uart
          this->write_array(this->tx_buffer_.data(), this->tx_buffer_.size());
          this->flush();
          this->tx_buffer_.clear();

          // signal flow control write mode disabled
          if (this->flow_control_pin_ != nullptr)
            this->flow_control_pin_->digital_write(false);

          // update device state
          if (this->devices_[this->last_zone_checked_index_]->write_update_pending == true)
          {
            ESP_LOGV(TAG, "Disabling write flag for zone %d", this->devices_[this->last_zone_checked_index_]->zone_number);
            this->devices_[this->last_zone_checked_index_]->write_update_pending = false;
          }

          // update state for last request
          this->last_request_zone_ = this->devices_[this->last_zone_checked_index_]->zone_number;
          this->receive_until_time_ = millis() + this->receive_wait_time_;

          // update state machine
          this->state_ = State::PROCESS_DEVICE_STATUS_START;
        }

        // will overflow back to 0 when it reaches the top
        // todo: implement this properly in the protocol
        // this->last_request_id_++;
        return;
      }

      // handle reading timeouts
      if ((this->receive_until_time_ - millis()) > this->receive_wait_time_)
      {
        ESP_LOGE(TAG, "Last receive time exceeded. Clearing buffer...");
        clear_rx_buffer();

        this->state_ = State::REQUEST_NEXT_DEVICE_STATUS;
        return;
      }

      if (this->available())
      {
        // read byte and process
        uint8_t c;
        read_byte(&c);
        ESP_LOGV(TAG, "Received Byte  %d (0X%x)", c, c);

        // read the start of a new response
        if (this->state_ == State::PROCESS_DEVICE_STATUS_START)
        {
          ESP_LOGV(TAG, "PROCESS_DEVICE_STATUS_START");

          // handle valid start of response
          if (c == 0x10 && this->rx_buffer_.size() == 0)
          {
            ESP_LOGV(TAG, "Received start of new response");

            this->rx_buffer_.clear();
            this->rx_buffer_.push_back(c);

            this->state_ = State::PROCESS_DEVICE_STATUS_CONTINUE;
          }
          // handle invalid start of response
          else
          {
            ESP_LOGE(TAG, "Received invalid start of response. Clearing buffer...");
            clear_rx_buffer();
            this->state_ = State::REQUEST_NEXT_DEVICE_STATUS;
          }

          return;
        }

        if (this->state_ == State::PROCESS_DEVICE_STATUS_CONTINUE)
        {
          ESP_LOGV(TAG, "PROCESS_DEVICE_STATUS_CONTINUE");

          // add byte to rx buffer
          this->rx_buffer_.push_back(c);

          // valid climate responses are kmillis()n to be 16 bytes long with the first byte being 0x10 (16), response length of 16 bytes and the last byte being the checksum
          if (this->rx_buffer_.size() == 16)
          {
            // handle bad checksum
            if (calculate_checksum(this->rx_buffer_) != this->rx_buffer_[this->rx_buffer_.size() - 1])
            {
              // todo: include response bytes in printout
              ESP_LOGD(TAG, "Checksum failed for response");
              clear_rx_buffer();

              this->state_ = State::REQUEST_NEXT_DEVICE_STATUS;
              return;
            }

            // TODO: add a flag to ignore out of order responses
            // check to see if the response is for the last request (request/response is in order)
            if (this->rx_buffer_[4] == this->last_request_zone_ && (this->rx_buffer_[2] == (this->last_request_id_ - 1) || this->rx_buffer_[2] == (this->last_request_id_)))
            {
              // notify valid device components
              for (auto &device : this->devices_)
              {
                if (device->zone_number == this->rx_buffer_[4])
                {
                  ESP_LOGD(TAG, "Valid message. Notifying zone %d...", this->last_request_zone_);
                  device->on_message_received(this->rx_buffer_);
                }
              }
            }
            else
            {
              ESP_LOGD(TAG, "Response does not match last request ID. Ignoring...");
              ESP_LOGV(TAG, "rx_buffer[2] (%d) == last_request_id_   (%d)", this->rx_buffer_[2], (this->last_request_id_ - 1));
              ESP_LOGV(TAG, "rx_buffer[4] (%d) == last_request_zone_ (%d)", this->rx_buffer_[4], this->last_request_zone_);
            }

            // reset state
            clear_rx_buffer();
            this->state_ = State::REQUEST_NEXT_DEVICE_STATUS;
            return;
          }
        }
      }
    }


  } // namespace lgap
} // namespace esphome