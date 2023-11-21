# LG Airconditioner Protocol (LGAP)

**This protocol.md follows the same format as the LG Wall Controller protocol spec produced by JanM321 [here](https://github.com/JanM321/esphome-lg-controller/blob/main/protocol.md).**

As discussed in the original [README](./README.md), this protocol is used to allow LG HVAC Outdoor Units (ODU) to communicate with protocol gateways - generally used for Building Management System (BMS) integration. There are a number of official gateways supporting Modbus RTU, LonWorks, BACnet and more. There are also 3rd party gateways, including those produced by Intesis that enable other protocols such as KNX.

By implementing this protocol directly, my own learning process outcome is to build either a Home Assistant native driver that can leverage an RS485 to TCP bridge, or an esphome driver that will expose a native Climate entity and handle the protocol translation.

## Overview

The LGAP protocol leverages an RS485 interface at a baud rate of 4,800 bps at 8N1. The physical pins are generally either Central Control (CENA/CENB) or the output pins of a PI-485 expansion board. To my knowledge right now, the ODU does not voluntarily send state updates. Instead values must be polled from the ODU by sending 8 byte requests.

**IMPORTANT: All temperatures sent and received are in degrees celsius.**

## Unknown Values

There are still plenty of values I'm not sure of. One thing that helps a lot however, is referring to the Modbus registers of the official LGAP->Modbus RTU gateway: PMBUSB00A. Appendix 1 of the [Installation Guide](https://api.library.loxone.com/downloader/file/246/LG%20PMBUSB00A%20%20Installation%20guide.pdf) has all the possible values that can be read and written through the Modbus gateway. This tells us that all these settings should be available to use through the LGAP request/response messages.

If anyone would like to propose settings to investigate from this list against any of the bytes below, I'd more than welcome the help and insights!

## Checksum

The checksum formula seems to be the same as what is used in the LG Wall Controller Protocol - which is promising. It can be calculated like follows:

1. Sum all non-checksum bytes (packet length - 1)
2. Modulo by 256 if you are using a non-overflow type. This step is optional in most languages if you are using the byte type, but it's a harmless step to have in place regardless
3. XOR by 0x55 (hex) or 85 (dec)

### Example - Sample Request

Input bytes: ```0  0  160  0  0  0  8 | 253```

Checksum: ```(168 % 256 ^ 85) = 253```

### Example - Sample Response

Input bytes: ```16  2  160  64  0  0  16  72  121  127  127  40  0  24  51 | 97```

Checksum: ```(745 % 256 ^ 85) = 97```

## Message Format

From what I've found so far, there is a single 8 byte request message which returns a single 16 byte response message.

#### LGAP Request

The request message is used to query the current state of the specified zone or Indoor Unit (IDU). For ODUs with only a single IDU connected, you will use Zone Number 0. For ODUs with multiple IDUs attached, you will need to refer to the zone number programmed into each IDU and subtract 1 due to the zones being zero indexed. There are instructions on YouTube for retrieving the Zone Number from either the wall panel or remote.

It is also possible to send a desired state as part of the request message. If the R/W flag is set to Write, then the ODU will pass the request on to the relevant IDU and report back the new state. This allows us to change settings, then go back to Read mode for polling.

Format:

|Byte|Bits|Description|Possible Values|
|--|--|--|--|
|0|```0000_0000```|Unknown|*|
|1|```0000_0000```|Unknown|*|
|2|```0000_0000```|Unknown|*|
|3|```0000_0000```|Zone Number|0-255|
|4|```0000_0000```|Request Type|0: Read<br/>2: Write|
||```0000_0000```|Request Type||
|5|```0000_00XX```|Mode|0: Cool<br/>1: Dehumidify<br/>2: Fan<br/>3: Auto<br/>4: Heat|
||```000X_XX00```|Swing|0: Off<br/>1: On|
||```XXX0_0000```|Fan Speed|0: Low<br/>1: Medium<br/>3: High|
|6|```0000_0000```|Target Temperature|1-10**|
|7|```0000_0000```|Checksum|0-255|

<br/>

_* Byte 0,1,2 I have written a script to send every value 0-255 on each of these bytes and recorded the values that returned responses with valid checksums. This may help to figure out the important bytes/acceptable values. [Byte 0 Analysis](./ref/lgap-req-0.csv), [Byte 1 Analysis](./ref/lgap-req-1.csv), [Byte 2 Analysis](./ref/lgap-req-2.csv)_

_** Byte 6 / Target Temperature is sent by taking the expected temperature and subtracting 15. The minimum temperature is 16 and maximum temperature is 30. Therefore the lowest value to send would be 1. The result would be seeing 16 degrees reflected on the wall panel._