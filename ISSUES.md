# Open Issues Tracker — jourdant/esphome-lgap

Last reviewed: 2026-03-12

## Issues Fixed by PR #26

### #20 — CLIMATE_SCHEMA --> _CLIMATE_SCHEMA

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/20](https://github.com/jourdant/esphome-lgap/issues/20)
- **Reporter**: @goncalvespedro (Dec 2025)
- **Problem**: ESPHome 2025.11+ removed `climate.CLIMATE_SCHEMA`, causing compile error.
- **Status**: Fixed in PR #26 — migrated to `climate.climate_schema()`.
- **Action**: Comment + close after PR merge.
- **Comment**:
  > This is fixed in PR #26 — we migrated from `climate.CLIMATE_SCHEMA` to `climate.climate_schema()` which is the correct API for ESPHome 2025.11+. The suggested `_CLIMATE_SCHEMA` works but accesses a private/internal attribute — `climate_schema()` is the public replacement.

### #17 — Incorrect checksum example

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/17](https://github.com/jourdant/esphome-lgap/issues/17)
- **Reporter**: @TheUserOfGithub (Oct 2025)
- **Problem**: Checksum example in `protocol.md` says sum is 745 but actual sum of `[16, 2, 160, 64, 0, 0, 16, 72, 121, 127, 127, 40, 0, 24, 51]` is 820. The final checksum (97) happens to be correct only because `(820 % 256) ^ 85 = 97`.
- **Status**: Reporter is correct. Needs one-line fix in `protocol.md`.
- **Action**: Fix protocol.md, comment + close.
- **Comment**:
  > Good catch! You're absolutely right — the sum should be 820, not 745. Fixed in PR #26. Thanks for verifying the math.

### #7 — Nice Job - I will analyze

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/7](https://github.com/jourdant/esphome-lgap/issues/7)
- **Reporter**: @ChriD (May 2024)
- **Problem**: Temperature values off by a few degrees, mentions 0.5°C steps on their unit.
- **Status**: Temperature calculation fixed in PR #26 (formula: `(192 - raw) / 3.0`). 0.5°C steps may be model-specific.
- **Action**: Comment + close.
- **Comment**:
  > Thanks for the protocol analysis! PR #26 fixes the temperature calculation — the correct formula is `(192 - raw) / 3.0` which handles the integer encoding properly. The 0.5°C step difference may be model-specific — some LG units support half-degree steps while others are integer-only. If you're still seeing offset issues after the fix, it could be a different temperature encoding on your specific model.

---

## Feature Requests Worth Implementing

### #8 — Indoor Temperature Readings Override

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/8](https://github.com/jourdant/esphome-lgap/issues/8)
- **Reporter**: @bzumik1 (Jun 2024, 2 upvotes)
- **Problem**: Users want to override the room temperature reading sent to the AC with data from external sensors (e.g., Zigbee temp sensor in room center instead of wall panel sensor near ceiling).
- **Status**: Not implemented. The esphome-lg-controller project supports this. Requires identifying which TX byte carries the temperature override.
- **Priority**: High — most impactful feature request.
- **Action**: Implement in a future PR.
- **Comment**:
  > This is on our radar. PR #26 adds comprehensive sensor support and lock enforcement — temperature override is a natural next step. It likely involves setting a specific bit/byte in the LGAP write command to switch from 'wall sensor' to 'external sensor' mode and providing the temperature value. If anyone has protocol captures showing this in action, that would help.

---

## Hardware/Connectivity Help Requests

### #25 — Compatibility with LG Multi V?

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/25](https://github.com/jourdant/esphome-lgap/issues/25)
- **Reporter**: @simonepsp (Mar 2026)
- **Problem**: Multi V system, can see CEN_A/CEN_B pads on PCB but no header. Wants to know if they can use those pads directly.
- **Action**: Comment with guidance, keep open for community.
- **Comment**:
  > The CEN_A and CEN_B pads are the RS485 bus — that's where LGAP communication happens. You'd typically use a PI-485 module that connects to the ODU's central controller port (CN_CENTRAL), which provides the proper RS485 header. Soldering directly to CEN_A/CEN_B on the IDU PCB is risky and not recommended. For Multi V systems, the PI-485 usually connects to the outdoor unit's central controller bus, not the individual indoor unit boards.

### #24 — LG Therma V HN1639 NK1 communication with heat pump

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/24](https://github.com/jourdant/esphome-lgap/issues/24)
- **Reporter**: @lwfcfi-design (Feb 2026)
- **Problem**: Therma V heat pump uses +128 offset for setpoint temperature. Write commands put unit into service cooling mode. Different protocol behavior.
- **Action**: Keep open — valuable protocol research for heat pump support.
- **Comment**:
  > Thanks for the detailed protocol analysis! The +128 offset for heat pump setpoint and the 05:01/05:02 parameter mode switching are excellent findings. This confirms that Therma V heat pumps use a variant of LGAP with different byte semantics. If you can capture the full status frame when the unit is working correctly via the thermostat, comparing it byte-by-byte with the frame your write command produces would help identify what's different. The service cooling mode behavior suggests the unit interprets the command as a factory/diagnostic mode rather than a normal setpoint change.

### #21 — How to know if the ODU has LGAP?

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/21](https://github.com/jourdant/esphome-lgap/issues/21)
- **Reporter**: @Hoekr0 (Dec 2025, 1 comment)
- **Problem**: User with MU4R25 Multi split wants to connect directly to CN_CENTRAL without PI-485.
- **Action**: Comment + close as answered.
- **Comment**:
  > For the MU4R25, you need a PI-485 module connected to CN_CENTRAL on the ODU. Direct connection without PI-485 won't work because the CN_CENTRAL port expects the PI-485 to handle the RS485 protocol translation. The PI-485 has DIP switches to configure the communication mode — make sure LGAP mode is enabled (refer to the PI-485 installation manual for your specific ODU model). The MVC JIG connector is indeed only for service diagnostics.

### #12 — Help wanted communicating with MULTI V IV outdoor unit

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/12](https://github.com/jourdant/esphome-lgap/issues/12)
- **Reporter**: @espcurious (Jan 2025, 56 comments, 1 upvote)
- **Problem**: Multi V IV (LMU300HHV) getting no responses. All READ requests time out.
- **Action**: Keep open — very active community troubleshooting thread.

### #11 — Compatibility with ducted system?

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/11](https://github.com/jourdant/esphome-lgap/issues/11)
- **Reporter**: @Anoxym (Dec 2024)
- **Problem**: Ducted UUD3 U30 / UM36F N20 system with PREMTB100 display. Wants to connect via RS485.
- **Action**: Comment with guidance.
- **Comment**:
  > Ducted systems use the same LGAP protocol over the PI-485 RS485 bus. Connect your ESP32 to the PI-485 module on the ODU (UUD3 U30), not to the existing Intensis controller. You can't share the RS485 bus with the Intensis — you'd need to choose one or the other. PR #26 adds `supports_auto_swing: true` which is particularly useful for ducted units to control airflow direction.

### #10 — PI485 LGAP + ATOM Lite & ATOMIC RS485 BASE not communicating

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/10](https://github.com/jourdant/esphome-lgap/issues/10)
- **Reporter**: @TerryFrench (Jul 2024, 56 comments, 1 upvote)
- **Problem**: A4UW30GFH0 ODU getting no responses despite correct wiring. Root cause was the PI-485 requires `tx_byte_0: 0x80` as the first byte — fixed by PR #15 (@tolkachev). Thread also uncovered that DIP switches 1,4,5 must be ON and IDUs need unique addresses set via the remote.
- **Status**: Resolved by PR #15. Key setup info extracted into README.md "PI-485 Expansion Board" section.
- **Action**: Comment + close.
- **Comment**:
  > This was resolved by PR #15 — the PI-485 requires `tx_byte_0: 0x80` as the first byte in the TX sequence. This is now the default in the current codebase. We've also added a dedicated "PI-485 Expansion Board" section to the README with DIP switch settings, IDU addressing steps, and LED troubleshooting. Thanks to everyone who contributed debugging info in this thread, especially @tolkachev for the fix and @TerryFrench, @greyburn, and @MaikaiLife for the extensive testing.

---

## Issues to Close (Off-Topic / Stale)

### #9 — LGMV?

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/9](https://github.com/jourdant/esphome-lgap/issues/9)
- **Reporter**: @evlo (Jul 2024)
- **Problem**: Asking about LGMV diagnostic port, not LGAP.
- **Action**: Comment + close.
- **Comment**:
  > LGMV is a separate diagnostic interface from LGAP — it uses different signaling and protocol. This project only supports LGAP via PI-485 RS485. The LGMV port on the IDU board is for LG's service tool software and isn't compatible with this component.

### #4 — Lilygo T-RSC3 Question

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/4](https://github.com/jourdant/esphome-lgap/issues/4)
- **Reporter**: @jourdant (Mar 2024, moved from #1)
- **Problem**: Unrelated Modbus/MPPT solar charger question that was moved out of #1. Note: the Lilygo T-RSC3 itself is documented in `background.md` as part of the Modbus Gateway (PMBUSB00A) setup, but its onboard RS485 is listed as "not compatible" for direct LGAP use.
- **Action**: Close.
- **Comment**:
  > Closing as this is unrelated to the LGAP component — it's about a Modbus MPPT solar controller. Note that the Lilygo T-RSC3's onboard RS485 interface is not compatible with LGAP (see the device table in the README). For general RS485 questions, the ESPHome community forums would be a better venue.

### #3 — How to send command?

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/3](https://github.com/jourdant/esphome-lgap/issues/3)
- **Reporter**: @CS012019 (Mar 2024)
- **Problem**: User manually constructing LGAP bytes incorrectly.
- **Action**: Comment + close.
- **Comment**:
  > The LGAP component handles all command formatting automatically — you don't need to construct raw bytes. Just add zones in your YAML config and use Home Assistant's climate controls. The protocol details are fully documented in `protocol.md` if you're building your own implementation. Your byte sequence was incorrect because the request format is `[tx_byte_0, 0x00, 0xFA, zone, mode_byte, temp_byte, fan_byte, checksum]`.

### #1 — Interesting project!

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/1](https://github.com/jourdant/esphome-lgap/issues/1)
- **Reporter**: @bzumik1 (Feb 2024, 13 comments)
- **Problem**: General discussion / offer to test.
- **Action**: Can close — served its purpose.

---

## Keep Open (Owner-Managed)

### #2 — LG Therma V before 2019

- **Link**: [https://github.com/jourdant/esphome-lgap/issues/2](https://github.com/jourdant/esphome-lgap/issues/2)
- **Reporter**: @nedyarrd (Mar 2024, assigned to @jourdant)
- **Problem**: Older Therma V can't communicate via Modbus.
- **Action**: Leave as-is — assigned to repo owner.

---

## Priority Summary


| Priority             | Issues                          | Action                                 |
| -------------------- | ------------------------------- | -------------------------------------- |
| Fix now              | #17 (checksum typo)             | One-line fix in protocol.md            |
| Close after PR merge | #20, #7                         | Comment noting PR #26 fixes them       |
| Implement next       | #8 (temp override)              | High-value feature for future PR       |
| Comment + close      | #10, #21, #9, #4, #3, #1       | Provide guidance / note resolution     |
| Keep open            | #25, #24, #12, #11, #2         | Active discussion or valuable research |


