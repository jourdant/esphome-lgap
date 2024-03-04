#include "lgap_device.h"
#include <vector>

namespace esphome
{
  namespace lgap
  {
    // float LGAPDevice::get_setup_priority() const { return setup_priority::DATA + 10; }

    void LGAPDevice::on_message_received(std::vector<unsigned char> &message)
    {
      this->handle_on_message_received(message);
    }

    void LGAPDevice::generate_lgap_request(std::vector<unsigned char> &message)
    {
      this->handle_generate_lgap_request(message);
    }


  } // namespace lgap
} // namespace esphome