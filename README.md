## Disclaimer
This whole exercise has been for my own personal learning and experimentation. There are aspects of integrating with high voltage equipment and looking into unpublished protocols. Attempting anything detailed here is at your own risk, may void the warranty of your unit or worse may result in physical harm.

<br/>

## Introduction

This journey started with a need to surface my LG Multi-V S heatpump locally (IE, no cloud connection) within Home Assistant.

<br/>

### Inspiration

I found an amazing project [JanM321/esphome-lg-controller](https://github.com/JanM321/esphome-lg-controller) that essentially plugs into the indoor unit using the wall controller pins and speaks the protocol required to read/update state from the indoor unit.

I was able to confirm this would work in my use-case as I had the same wall panel (PREMTB001) and was able to capture the bytes and decode them correctly. You can read on those efforts here: [First Discussion](https://github.com/JanM321/esphome-lg-controller/issues/1#issuecomment-1636972289) and [Second Discussion](https://github.com/JanM321/esphome-lg-controller/issues/2).

While this approach worked well for me, I wanted to be able to use the original panels on the wall at the same time. Ideally I'd also like to only have a single integration instead of putting an ESP32 in the wall for each of the four zones/controllers I have.

One day [a video](https://www.youtube.com/embed/Xuj2YFZ5zME?si=3Ovf-9DifcNpapcV) pops up on my YouTube recommendations from [Rod McBain](https://www.youtube.com/@RodMcBain) detailing an approach for interfacing with an LG outdoor unit using Modbus directly. After further research I found that my unit - LG Multi-V S did not have a direct modbus interface like Rod's LG Therma V. But this was enough to set me down the path of attempting direct integration with the outdoor unit.

<br/>

### Direct Integration Options

It turns out for many LG outdoor units there are three primary ways to enable central control:

1. **Onboard Modbus** - unfortunately for my particular unit (Multi-V S), this was not a function I could find. 

2. **Onboard Central Control pins** - some units have pins labeled Central Control or CENA and CENB. This is an RS485 interface, but speaks a custom protocol called LGAP (which seems to stand for something like LG Airconditioner Protocol). More on LGAP later, but there is no published spec that I've been able to find.

3. [**PI-485 extension board**](https://www.lgvrf.ca/en/products/pi~485) - for older units, you can use the PI-485 board which can attach to pins inside the unit and present an RS485 interface that speaks LGAP as described above.

4. [**PMBUSB00A Modbus gateway**](https://api.library.loxone.com/downloader/file/246/LG%20PMBUSB00A%20%20Installation%20guide.pdf) - this device can take the Central Control/LGAP interface and publish a set of standard modbus registers as a result. For my use case with a Multi-V S, I could in theory wire this directly to the central control pins and control it via modbus!

5. There are also other alternative units that LG provide as first party units for BMS integration using protocols such as LonWorks, BACnet and more.

<br/>

### Starting with PMBUSB00A
I managed to source one of these gateways and wire it up to the outdoor unit. It was really easy as the [installation guide](https://api.library.loxone.com/downloader/file/246/LG%20PMBUSB00A%20%20Installation%20guide.pdf) provided plenty of detail for the wiring and the detailing of the Modbus registers. 

For the integration between the PMBUSB00A and Home Assistant, I used a [LILYGO T-RSC3](https://www.lilygo.cc/products/t-rsc3) which is an ESP32 based board with a dedicated isolated RS485 and RS232 modules onboard. Being ESP32 based means that I can flash the device with esphome and use the yaml modbus definitions to publish live entities to Home Assistant with no custom code!

![wiring with T-RSC3](./images/IMG_2713.jpg)

The other great benefit of this setup is that both devices could be powered from the same 12v supply. On my outdoor unit, there are 12v/ground pins right next to the Central Control pins. So convenient.

After flashing with esphome with my config which you can [view here](./ref/modbus_esphome.yaml), I successfully had entities showing in Home Assistant and they're fully compatible with automations and scenes! Keep in mind at this stage, it is not presenting a native Climate entity, but this is great progress.

![homeassistant](./images/PHOTO-2023-10-12-17-15-05.jpg)

You'll notice the temperatures haven't been normalised in that screenshot - they are done this way in modbus to account for decimals. You need to divide by 10 to receive the decimal value in degrees celsius.

<br/>

### Going direct with LGAP

Once I had the modbus gateway + esphome setup, I was pretty happy. I had a solution that allowed the wall panels to operate while still having immediate control (plus automations) through Home Assistant. 

**But... what if we could avoid the modbus gateway altogether and speak the LGAP protocol directly instead?**

I went into searching as much as I possibly could about the protocol. There are really limited amounts of information available publicly. But the fact that these gateways exist (including 3rd party ones from Intesis), tells me that the protocol can be reverse engineered. 

**New goal: build a driver for esphome that uses LGAP to communicate directly and presents a standard climate entity to Home Assistant.**

What we do know from public about LGAP information is the following:


|Name|Value|
|-------|-------|
|Interface|RS485|
|Baud Rate| 4,800 bps|
|Data Bits| 8 bits|
|Parity| No Parity|
|Stop Bits| 1 stop bit|
|Request Length| 8 bytes|
|Response Length| 16 bytes|

<br/>

#### LGAP Request

As mentioned, it seems that standard requests are 8 bytes in length. I haven't been able to decode all the bytes yet, but the following so far makes sense:

|Position|Sample Byte|Sample Binary|Setting|
|--|--|--|--|
|0|0|00000000|_Unknown_|
|1|0|00000000|_Unknown_|
|2|160|10100000|_Unknown_|
|3|0|00000000|Zone Address - 0|
|4|1|00000001|Request R/W - Read<br/>Power - On|
|5|0|00000000|Swing - Off<br/>Mode - Cool<br/>Speed - Low|
|6|8|00001000|Target Temp - 23|
|7|252|11111100|Checksum|

Setting request[4] to write instead of read will allow you to set the desired state of the Zone and you'll see the values reflected on the wall panels almost immediately.

I've run a script to test request[0,1,2] with values from 0 to 255 and saved the results in CSV files stored in this repository. If anyone is interested in helping to analyse these bytes for what these 3 request bytes may refer to, I'd love the help.

The following bytes were captured while Zone 0 was powered on and set to Cool, Low and 23 degrees celsius:

* [Request Index 0](./ref/lgap-req-0.csv)
* [Request Index 1](./ref/lgap-req-1.csv)
* [Request Index 2](./ref/lgap-req-2.csv)

<br/>

#### LGAP Response

If a bad request is sent with invalid values, the outdoor unit doesn't seem to respond with any bytes at all. If the request is valid, 16 bytes are returned and I've been able to decode the following:

|Position|Sample Byte|Sample Binary|Setting|
|--|--|--|--|
|0|16|00010000|_Response type or number of bytes to follow?_|
|1|3|00000011|Power - On<br/>_IDU Connected?_|
|2|160|10100000|_Seems to always match request[2]_|
|3|64|01000000|_Unknown_|
|4|0|00000000|Zone Address|
|5|0|00000000|_Unknown_|
|6|16|00010000|Swing - Off<br/>Mode - Cool<br/>Fan Speed - Medium|
|7|72|01001000|Target Temperature (Celsius) - 23|
|8|122|01111010|Room Temperature (Celsius) - 25|
|9|122|01111010|_Pipe In Temp?_ or<br/>_Target Temp Lower?_ - 25|
|10|122|01111010|_Pipe Out Temp?_ or<br/>_Target Temp Upper?_ - 25|
|11|40|00101000|_Unknown_|
|12|0|00000000|_Unknown_|
|13|24|00011000|_Unknown_|
|14|51|00110011|_Unknown_|
|15|121|01111001|Checksum|

In some cases, multiple values are stored in a single byte such as the fan speed, mode and swing consolidated into byte 6. 

After having implemented the Modbus Gateway previously, I know that there are many more values that can be extracted. These were values that were available as modbus registers, that I don't have the appropriate byte located for yet. The list of values we should be able to map are:

|Field Name|Expected Value|Predicted Byte|
|--|--|--|
|Error Code|0-255|
|Pipe In Temp|-99 to 99|Potentially 9|
|Pipe Out Temp|-99 to 99|Potentially 10|
|Target Temp Limit Upper|16-30|Potentially 9|
|Target Temp Limit Lower|16-30|Potentially 10|
|Indoor Unit Connected Status|0-1|Sharing 1|
|Alarm|0-1|
|Filter Alarm|0-1|
|Filter Alarm Release|0-1|
|Lock Remote Controller|0-1|
|Lock Operate Mode|0-1|
|Lock Fan Speed|0-1|
|Lock Target Temp|0-1|
|Lock Indoor Unit Address|0-1|

If you have additional insight into how I can best decode these messages - I'm more than happy to accept advice or contributions. I'm sharing what I have so far so that we can build out a native integration for Home Assistant.

Enjoy!