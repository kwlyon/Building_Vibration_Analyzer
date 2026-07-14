# Bill of Materials

| Item | Suggested part | Quantity | Notes |
| --- | --- | ---: | --- |
| Microcontroller | PJRC/SparkFun Teensy 4.1 with headers, DEV-16996 or equivalent | 1 | Use Teensy 4.1, not 4.0, for built-in microSD socket. |
| Accelerometer board | Analog Devices EVAL-ADXL355-PMDZ | 1 | User-confirmed board. |
| microSD card | Name-brand 8 GB to 32 GB, industrial preferred | 1 | Use fresh card for field data. |
| RGB LED | Common-cathode or common-anode discrete LED | 1 | Firmware compile-time setting selects polarity. |
| LED resistors | 680 ohm, 1/8 W or 1/4 W | 3 | Adjust only after measuring current. |
| Run/Stop pushbutton | Normally open momentary switch | 1 | Panel-mount preferred for field use. |
| RTC battery | CR2032 holder and CR2032 cell | 1 optional | Connect positive to VBAT and negative to GND. |
| PMOD cable or header wiring | Short 12-pin PMOD cable, ribbon, or discrete wires | 1 | Keep short unless buffered. |
| Enclosure | Small plastic or metal enclosure | 1 | Provide strain relief for USB and sensor cable. |
| Sensor puck/block | Small aluminum block or puck | 1 optional | Rigidly mount the ADXL355 board for repeatable coupling. |
| USB cable | USB data cable | 1 | Must support data, not charge-only. |

## Recommended bench equipment

- Digital multimeter for continuity and 3.3 V checks.
- Oscilloscope or logic analyzer for SPI and DRDY bring-up.
- Known vibration source or shaker for later dynamic validation.
- Small torque screwdriver if mounting the sensor board to a puck.
