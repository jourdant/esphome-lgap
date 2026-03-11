# LG Airconditioner Protocol (LGAP)

**This protocol.md follows the same format as the LG Wall Controller protocol spec produced by JanM321 [here](https://github.com/JanM321/esphome-lg-controller/blob/main/protocol.md).**

As discussed in the original [README](./README.md), this protocol is used to allow LG HVAC Outdoor Units (ODU) to communicate with protocol gateways - generally used for Building Management System (BMS) integration. There are a number of official gateways supporting Modbus RTU, LonWorks, BACnet and more. There are also 3rd party gateways, including those produced by Intesis that enable other protocols such as KNX.

By implementing this protocol directly, my own learning process outcome is to build either a Home Assistant native driver that can leverage an RS485 to TCP bridge, or an esphome driver that will expose a native Climate entity and handle the protocol translation.

## Overview

The LGAP protocol leverages an RS485 interface at a baud rate of 4,800 bps at 8N1. The physical pins are generally either Central Control (CENA/CENB) or the output pins of a PI-485 expansion board. To my knowledge right now, the ODU does not voluntarily send state updates. Instead values must be polled from the ODU by sending 8 byte requests.

**IMPORTANT: All temperatures sent and received are in degrees celsius.**

## Checksum

The checksum formula seems to be the same as what is used in the [LG Wall Controller Protocol](https://github.com/JanM321/esphome-lg-controller/blob/main/protocol.md) - which is promising. It can be calculated like follows:

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

### LGAP Request (TX Data - Controller → AC)

The request message is used to query the current state of the specified zone or Indoor Unit (IDU). For ODUs with only a single IDU connected, you will use Zone Number 0. For ODUs with multiple IDUs attached, you will need to refer to the zone number programmed into each IDU and subtract 1 due to the zones being zero indexed. There are instructions on YouTube for retrieving the Zone Number from either the wall panel or remote.

It is also possible to send a desired state as part of the request message. If the R/W flag is set to Write, then the ODU will pass the request on to the relevant IDU and report back the new state. This allows us to change settings, then go back to Read mode for polling.

Format:

|Byte|Bits|Description|Possible Values|
|--|--|--|--|
|0 (TX0)|```XXXX_XXXX```|Frame header/length|Configurable (typically 0x10)|
|1 (TX1)|```XXXX_XXXX```|Command type|0x00 for normal control|
|2 (TX2)|```XXXX_XXXX```|Command ID|0xA0 for set/control frame|
|3 (TX3)|```XXXX_XXXX```|Zone Number|0-255 (high nibble: Group, low nibble: Indoor Unit)|
|4 (TX4)|```0000_000X```|**ON** - Power State|0: Off<br/>1: On|
||```0000_00X0```|**EXE** - Execute/Write|0: Read only<br/>1: Write state|
||```0000_0X00```|**Lock** - Control Lock|0: Unlocked<br/>1: Locked (child lock)|
||```0000_X000```|Reserved|0|
||```000X_0000```|**Plasma** - Ion Control|0: Off<br/>1: On|
||```XXX0_0000```|Reserved|0|
|5 (TX5)|```0000_0XXX```|**Mode**|0: Cool<br/>1: Dry/Dehumidify<br/>2: Fan Only<br/>3: Auto (status only)<br/>4: Heat|
||```0000_X000```|**Auto Swing** (ducted)|0: Manual airflow<br/>1: Auto airflow|
||```0XXX_0000```|**Fan Speed**|0: No change<br/>1: Low<br/>2: Medium<br/>3: High<br/>4: Auto<br/>5: Slow/Quiet (optional)<br/>6: Power/Turbo (optional)<br/>7: Slow+Power (optional)|
||```X000_0000```|Reserved|0|
|6 (TX6)|```0000_XXXX```|Target Temperature|1-15 (Indoor set temp = value + 15°C)<br/>Valid range: 16-30°C|
|7 (TX7)|```XXXX_XXXX```|Checksum|(sum of TX0-TX6) XOR 0x55|

<br/>

**Notes:**

- **TX0 (Byte 0)**: Configurable frame header - typically 0x10 for standard data frames
- **TX1 (Byte 1)**: Command type - 0x00 for normal read/write operations
- **TX2 (Byte 2)**: Command ID - 0xA0 for control/set operations. This byte is echoed back in RX2 for response validation
- **TX3 (Byte 3)**: Zone addressing - high nibble represents group number, low nibble represents indoor unit number within that group
- **TX6 (Byte 6)**: Target temperature is sent by taking desired °C and subtracting 15. Example: 22°C → 22 - 15 = 7 (0x07)

**Temperature Limits per Mode:**
- Heat mode: 16-30°C (TX6 values: 1-15)
- Cool/Dry/Fan/Auto modes: 18-30°C (TX6 values: 3-15)


### LGAP Response (RX Data - AC → Controller)

So far from all requests I've sent over the interface, it has always been either 16 bytes or 0 bytes returned. If the request is invalid, 0 bytes are returned.

Format:

|Byte|Bits|Description|Possible Values|Notes|
|--|--|--|--|--|
|0 (RX0)|```XXXX_XXXX```|Header/Length|0x10 (16)|Frame header|
|1 (RX1)|```0000_000X```|**ON** - Power State|0: Off<br/>1: On||
||```0000_00X0```|IDU Connected Status|0: Not connected<br/>1: Connected||
||```0000_0X00```|**Lock** - Control Lock|0: Unlocked<br/>1: Locked||
||```000X_0000```|**Plasma** - Ion Status|0: Off<br/>1: On||
||```XXX0_X000```|Reserved/Unknown|||
|2|```XXXX_XXXX```|Request Echo|Matches TX2 (request ID)|Used to validate response|
|3|```XXXX_XXXX```|Unknown|||
|4|```XXXX_XXXX```|Zone Number|0-255|Matches requested zone|
|5 (RX5)|```XXXX_XXXX```|**Error Code**|0: No error<br/>1-255: Service codes|LG error/alarm codes|
|6 (RX6)|```0000_0XXX```|**Mode**|0: Cool<br/>1: Dry/Dehumidify<br/>2: Fan Only<br/>3: Auto<br/>4: Heat||
||```0000_X000```|**Swing** (Auto Airflow)|0: Manual<br/>1: Auto|For ducted units|
||```0XXX_0000```|**Fan Speed**|0-7|See TX5 for mappings|
||```X000_0000```|Reserved|||
|7 (RX7)|```XXXX_XXXX```|**Target Temperature**|Raw 0-255|(value & 0x0F) + 15 = °C<br/>Valid: 16-30°C|
|8 (RX8)|```XXXX_XXXX```|**Room Temperature**|Raw 0-255|(192 - value) / 3 = °C|
|9 (RX9)|```XXXX_XXXX```|**Pipe In Temperature**|Raw 0-255|(192 - value) / 3 = °C|
|10 (RX10)|```XXXX_XXXX```|**Pipe Out Temperature**|Raw 0-255|(192 - value) / 3 = °C|
|11 (RX11)|```XXXX_XXXX```|**Zone Active Load**|0-255|Dynamic load index<br/>LonWorks `nvoLoadEstimate`<br/>204 = idle, lower = higher load|
|12 (RX12)|```XXXX_XXXX```|**Zone Power State Flag**|0: Running<br/>1: Off/Idle|LonWorks `nvoOnOff`<br/>May jitter during transitions|
|13 (RX13)|```XXXX_XXXX```|**Zone Design Load Index**|0-255|Fixed capacity/duct size<br/>LonWorks `nciRatedCapacity`<br/>e.g., 9, 12, 24, 36...|
|14 (RX14)|```XXXX_XXXX```|**ODU Total Load**|0-255|System-wide load index<br/>LonWorks `nvoThermalLoad`<br/>~Sum of active zone loads|
|15 (RX15)|```XXXX_XXXX```|Checksum|0-255|(sum of RX0-RX14) XOR 0x55|

<br/>

### Temperature Conversion Formulas

#### Target Temperature (RX7):
```
Celsius = (raw_byte & 0x0F) + 15
```
Example: `0x17 → (0x17 & 0x0F) + 15 = 7 + 15 = 22°C`

#### Room, Pipe In, Pipe Out Temperature (RX8, RX9, RX10):
```
Celsius = (192 - raw_byte) / 3
```
Example: `0x66 (102) → (192 - 102) / 3 = 30°C`

### LonWorks Protocol Mapping

Bytes 11-14 align perfectly with LG's LonWorks BMS integration protocol:

|LGAP Byte|ESPHome Name|LonWorks Field|Purpose|
|--|--|--|--|
|11|Zone Active Load|`nvoLoadEstimate` / `nvoUnitLoad`|Dynamic real-time load per zone|
|12|Zone Power State|`nvoOnOff`|Zone ON/OFF boolean|
|13|Zone Design Load|`nciRatedCapacity`|Fixed design capacity weight|
|14|ODU Total Load|`nvoThermalLoad` / `nvoOduLoadFactor`|Total compressor load|

These bytes enable advanced energy monitoring, load balancing analysis, and compressor duty cycle tracking.


## Mapped Features ✅

The following features from the PMBUSB00A Modbus gateway ([Installation Guide](https://api.library.loxone.com/downloader/file/246/LG%20PMBUSB00A%20%20Installation%20guide.pdf)) have been successfully mapped and implemented:

### Implemented in ESPHome Component

|Feature|Request Byte|Response Byte|Status|
|--|--|--|--|
|Power State (ON/OFF)|TX4 bit0|RX1 bit0|✅ Implemented|
|Mode (Cool/Heat/Dry/Fan/Auto)|TX5 bits 0-2|RX6 bits 0-2|✅ Implemented|
|Fan Speed (Low/Medium/High/Auto/Quiet/Turbo)|TX5 bits 4-6|RX6 bits 4-6|✅ Implemented|
|Target Temperature (16-30°C)|TX6|RX7|✅ Implemented|
|Room Temperature|N/A|RX8|✅ Implemented|
|Pipe In Temperature|N/A|RX9|✅ Implemented|
|Pipe Out Temperature|N/A|RX10|✅ Implemented|
|Auto Swing / Auto Airflow|TX5 bit3|RX6 bit3|✅ Implemented (optional)|
|Control Lock (Child Lock)|TX4 bit2|RX1 bit2|✅ Implemented|
|Plasma Ion Control|TX4 bit4|RX1 bit4|✅ Implemented (optional)|
|Error/Alarm Code|N/A|RX5|✅ Implemented|
|Zone Active Load (dynamic)|N/A|RX11|✅ Implemented|
|Zone Power State Flag|N/A|RX12|✅ Implemented|
|Zone Design Load (capacity)|N/A|RX13|✅ Implemented|
|ODU Total Load|N/A|RX14|✅ Implemented|

### Advanced Lock Features (ESPHome-Specific)

The ESPHome implementation includes additional lock features beyond the basic protocol:

|Feature|Implementation|Status|
|--|--|--|
|Lock Temperature|Software enforcement|✅ Implemented|
|Lock Fan Speed|Software enforcement|✅ Implemented|
|Lock Mode|Software enforcement|✅ Implemented|
|Power Only Mode|Software enforcement|✅ Implemented|
|Wall Controller Lock Enforcement|Automatic revert on unauthorized changes|✅ Implemented|

### Sleep Timer (ESPHome-Specific)

|Feature|Implementation|Status|
|--|--|--|
|Sleep Timer (0-420 minutes)|Number input + automatic shutoff|✅ Implemented|
|Timer Remaining|Countdown sensor|✅ Implemented|

<br/>

## Unmapped / Unknown Values

The following features from the Modbus gateway specification have not yet been mapped to specific LGAP bytes:

### Potentially Available but Not Yet Mapped

|Description|Possible Location|Notes|
|--|--|--|
|Filter Alarm Release|Request (unknown byte)|Write command to clear filter alarm|
|Filter Alarm Status|Response (unknown byte)|Read-only flag for filter maintenance|
|Lock Indoor Unit Address|Request/Response (unknown)|Prevent zone number changes|
|Target Temperature Limits|Response (unknown)|Min/max temperature constraints per mode|

### Reserved Bits

|Location|Bits|Status|
|--|--|--|
|TX4|bit3, bits 5-7|Reserved (always 0)|
|TX5|bit7|Reserved (always 0)|
|RX1|bit3, bits 5-7|Unknown/Reserved|
|RX2|All bits|Echo of TX2, not decoded|
|RX3|All bits|Unknown function|
|RX6|bit7|Reserved|

<br/>

## Protocol Implementation Notes

### Polling Strategy

The ODU does not voluntarily send state updates. You must continuously poll each zone:

1. Send read request (TX4 bit1 = 0) for zone
2. Parse 16-byte response
3. Update internal state
4. Wait appropriate interval (recommend 1-5 seconds between zones)
5. Repeat for next zone

### Write Operations

To change settings:

1. Set TX4 bit1 = 1 (EXE/Write flag)
2. Set desired state in TX4-TX6
3. Send request
4. Parse response to confirm new state
5. Return to read-only mode (TX4 bit1 = 0) for subsequent polls

### Multi-Zone Management

For systems with multiple zones:
- Use same LGAP interface for all zones
- Poll each zone sequentially using TX3 (zone number)
- Share load monitoring data (RX14 is identical across all zones on same ODU)
- Coordinate mode changes (all zones must use same heating/cooling mode)

### Temperature Conversions

**Critical**: Do not use simple `(raw & 0x0F) + 15` for all temperatures!

- **Target temp (RX7)**: `(raw & 0x0F) + 15` ✅
- **Room/Pipe temps (RX8-10)**: `(192 - raw) / 3` ✅

Using the wrong formula results in wildly inaccurate readings.

### Lock Enforcement

Protocol only supports basic control lock (TX4 bit2). Advanced lock features (temperature lock, fan lock, mode lock, power-only mode) must be implemented in software by:

1. Storing previous state when lock activated
2. Blocking HA control requests when locked
3. Detecting unauthorized wall controller changes in RX messages
4. Sending write command to revert to locked state

### Error Handling

- Invalid requests return 0 bytes (timeout)
- Check RX5 for error codes on every response
- Validate checksum before processing response data
- Verify RX2 matches TX2 to confirm response correlation
- Handle zone not found (0-byte response) gracefully

### Load Monitoring Best Practices

Bytes RX11-14 provide valuable load data:

```python
# Zone efficiency (0-1, where 1 = maximum load)
zone_efficiency = (204 - rx11) / 204

# Zone power consumption estimate
zone_power_kw = zone_efficiency * zone_design_load_kw

# System load percentage
system_load_pct = (rx14 / sum_of_all_design_loads) * 100

# Compressor duty cycle indicator
compressor_active = rx14 > 0 and any(rx12 == 0)
```

## Contributing

If you discover any additional mappings or can help decode the remaining unknown bytes, please contribute! The protocol is well-documented now, and any improvements will benefit all users.

### How to Contribute

1. Fork the repository
2. Test new byte mappings thoroughly across multiple zones and modes
3. Document your findings with examples and observations
4. Submit a pull request with updated protocol.md
5. Include sample packet captures if possible

All contributions are welcome, whether it's fixing typos, improving documentation, or discovering new protocol features!