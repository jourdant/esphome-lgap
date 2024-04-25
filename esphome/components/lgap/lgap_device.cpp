#include "lgap_device.h"
#include <vector>

namespace esphome
{
  namespace lgap
  {
    // float LGAPDevice::get_setup_priority() const { return setup_priority::DATA + 10; }

    void LGAPDevice::on_message_received(std::vector<uint8_t> &message)
    {
      this->handle_on_message_received(message);
    }

    void LGAPDevice::generate_lgap_request(std::vector<uint8_t> &message, uint8_t &request_id)
    {
      this->handle_generate_lgap_request(&message, &request_id);
    }


  } // namespace lgap
} // namespace esphome