# LG Airconditioner Protocol (LGAP)

**This protocol.md follows the same format as the LG Wall Controller protocol spec produced by JanM321 [here](https://github.com/JanM321/esphome-lg-controller/blob/main/protocol.md).**

As discussed in the original [README](./README.md), this protocol is used to allow LG HVAC Outdoor Units (ODU) to communicate with protocol gateways - generally used for Building Management System (BMS) integration. There are a number of official gateways supporting Modbus RTU, LonWorks, BACnet and more. There are also 3rd party gateways, including those produced by Intesis that enable other protocols such as KNX.

By implementing this protocol directly, my own learning process outcome is to build either a Home Assistant native driver that can leverage an RS485 to TCP bridge, or an esphome driver that will expose a native Climate entity and handle the protocol translation.

## Overview

The LGAP protocol leverages an RS485 interface at a baud rate of 4,800 bps at 8N1. The physical pins are generally either Central Control (CENA/CENB) or the output pins of a PI-485 expansion board. To my knowledge right now, the ODU does not voluntarily send state updates. Instead values must be polled from the ODU by sending 8 byte requests.

**IMPORTANT: All temperatures sent and received are in degrees celsius.**

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

**^ = XOR**

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
|3|```XXXX_XXXX```|Zone Number|0-255|
|4|```0000_000X```|Power State|0: Off<br/>1: On|
||```0000_00X0```|Request Type|0: Read<br/>1: Write|
||```XXXX_XX00```|Unknown||
|5|```0000_00XX```|Mode|0: Cool<br/>1: Dehumidify<br/>2: Fan<br/>3: Auto<br/>4: Heat|
||```000X_XX00```|Swing|0: Off<br/>1: On|
||```XXX0_0000```|Fan Speed|0: Low<br/>1: Medium<br/>2: High|
|6|```0000_XXXX```|Target Temperature|1-10**|
|7|```XXXX_XXXX```|Checksum|0-255|

<br/>

_* Byte 0,1,2 - I've written a script to send every value 0-255 on each of these bytes and recorded the values that returned responses with valid checksums. This may help to figure out the important bytes/acceptable values. [Byte 0 Analysis](./ref/lgap-req-0.csv), [Byte 1 Analysis](./ref/lgap-req-1.csv), [Byte 2 Analysis](./ref/lgap-req-2.csv)_

_** Byte 6 - Target Temperature is sent by taking the expected temperature and subtracting 15. The minimum temperature is 16 and maximum temperature is 30. Therefore the lowest value to send would be 1. The result would be seeing 16 degrees reflected on the wall panel._


### LGAP Response

So far from all requests I've sent over the interface, it has always been either 16 bytes or 0 bytes returned. If the request is invalid, 0 bytes are returned. 

The values in _italics_ are possible values that I haven't proven yet.

Format:

|Byte|Bits|Description|Possible Values|
|--|--|--|--|
|0|```XXXX_XXXX```|_Response Length?_ or<br/>_Response Type?_|Always 16|
|1|```0000_000X```|Power State|0: Off<br/>1: On|
||```0000_00X0```|_IDU Connected?_|0: False<br/>1: True|
||```XXXX_XX00```|Unknown||
|2|```XXXX_XXXX```|Unknown|Always matches request[2]*|
|3|```0000_0000```|Unknown||
|4|```XXXX_XXXX```|Zone Number|0-255|
|5|```0000_0000```|Unknown||
|6|```0000_0XXX```|Mode|Mode|0: Cool<br/>1: Dehumidify<br/>2: Fan<br/>3: Auto<br/>4: Heat|
||```0000_X000```|Swing|0: Off<br/>1: On|
||```0XXX_0000```|Fan Speed|0: Low<br/>1: Medium<br/>2: High|
||```X000_0000```|Unknown||
|7|```XXXX_XXXX```|Target Temperature|0-255**|
|8|```XXXX_XXXX```|Room Temperature|0-255**|
|9|```XXXX_XXXX```|_Pipe In Temp?_ or<br/>_Target Temp Lower?_|0-255**|
|10|```XXXX_XXXX```|_Pipe Out Temp?_ or<br/>_Target Temp Upper?_|0-255**|
|11|```0000_0000```|Unknown||
|12|```0000_0000```|Unknown||
|13|```0000_0000```|Unknown||
|14|```0000_0000```|Unknown||
|15|```XXXX_XXXX```|Checksum|0-255|

<br/>

_* Byte 2 - This value so far always seems to match the byte from request[2]. Potentially this can be used as a way to validate the response for a given request?_

_** Byte 6,7,8?,9? - Temperature values are calculated by taking the number and doing a bitwise AND with 0xF (15) then adding 15. Sample: ```(122 & 15) + 15 = 25 degrees celsius```._


## Unknown Values

There are still plenty of values I'm not sure of. One thing that helps a lot however, is referring to the Modbus registers of the official LGAP->Modbus RTU gateway: PMBUSB00A. Appendix 1 of the [Installation Guide](https://api.library.loxone.com/downloader/file/246/LG%20PMBUSB00A%20%20Installation%20guide.pdf) has all the possible values that can be read and written through the Modbus gateway. This tells us that all these settings should be available to use through the LGAP request/response messages.

<br/>

### Unmapped Request Values

|Description|Possible Values|Possible Byte|
|--|--|--|
|Filter Alarm Release|0-1||

<br/>

### Unmapped Response Values

|Description|Possible Values|Possible Byte|
|--|--|--|
|Error Code|0-255||
|Pipe In Temperature|-99-99|request[9,10]|
|Pipe Out Temperature|-99-99|request[9,10]|
|Target Temperature Limit Lower|-99-99|request[9,10]|
|Target Temperature Limit Upper|-99-99|request[9,10]|
|Indoor Unit Connected Status|0-1|request[1]|
|Alarm Activated|0-1||
|Filter Alarm Activated|0-1||
|Lock Remote Controller|0-1||
|Lock Operate Mode|0-1||
|Lock Fan Speed|0-1||
|Lock Target Temperature|0-1||
|Lock Indoor Unit Address|0-1||

<br/>

If anyone would like to propose settings to investigate from this list against any of the bytes below, I'd more than welcome the help and insights!