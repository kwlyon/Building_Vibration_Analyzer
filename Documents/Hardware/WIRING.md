# Wiring

## Voltage and power

Teensy 4.1 and the EVAL-ADXL355-PMDZ are 3.3 V logic devices. Do not connect any ADXL355 PMOD signal to 5 V. Teensy 4.1 I/O pins are not 5 V tolerant.

Power the EVAL-ADXL355-PMDZ from Teensy 3.3 V and GND:

- PMOD pins 6 and 12 to Teensy 3.3 V.
- PMOD pins 5 and 11 to Teensy GND.

Use short, low-impedance ground wiring between Teensy and the sensor head. If the sensor is placed in a metal puck or block, tie shield/drain to chassis at one end only unless testing shows a better grounding scheme.

## SPI sensor connection

Wire the PMOD connector as shown in `PIN_ASSIGNMENTS.md`. Configure SPI as:

- Mode: 0.
- SCLK: start at 1 MHz for bring-up; ADXL355 allows higher rates, but remote wiring usually benefits from slower edges.
- CS idle high.
- Read command byte: register address shifted left one bit with the read bit set.
- Write command byte: register address shifted left one bit with the read bit clear.

For a remote sensor head, keep the unbuffered SPI cable under roughly 15 cm to 30 cm for first prototypes. Use twisted pairs or a ribbon cable with interleaved grounds if possible. If the cable must be longer, reduce SCLK, add series damping resistors near Teensy, and consider differential signaling or a small remote microcontroller.

## DATA_RDY and interrupt pins

Connect ADXL355 DRDY to Teensy pin 2. DRDY is used to signal that a fresh sample is ready, so the firmware avoids timing acquisition with `delay()`.

INT1 and INT2 are wired but optional. The firmware can use them later for FIFO watermark, activity, or overrun status.

## RGB LED

Use one discrete RGB LED with three current-limiting resistors.

Suggested starting values:

- Red: 680 ohm.
- Green: 680 ohm.
- Blue: 680 ohm.

These conservative values keep current near the Teensy recommended digital output range. If a brighter panel LED is needed, use a transistor/MOSFET driver instead of sourcing or sinking LED current directly from the Teensy.

The firmware supports common-cathode or common-anode with the `LED_COMMON_ANODE` compile-time setting.

## Run/Stop button

Wire one side of a normally open pushbutton to Teensy pin 8 and the other side to GND. Firmware enables `INPUT_PULLUP`, so the idle level is high and a pressed button reads low.

The firmware debounces in software and enforces a minimum interval between run/stop transitions.

## microSD

Use the Teensy 4.1 built-in microSD socket. Format cards as FAT32 or exFAT using a standard SD formatter. The firmware creates a new numbered CSV file for each acquisition and uses buffered writes with controlled periodic flushes.

## USB serial

Use the Teensy's main USB device connector. The serial protocol is a USB virtual COM port, not physical RS-232. Do not connect RS-232 voltage-level equipment directly to Teensy I/O pins.
