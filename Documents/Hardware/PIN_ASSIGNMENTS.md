# Pin Assignments

Target hardware:

- Teensy 4.1 / SparkFun DEV-16996.
- Analog Devices EVAL-ADXL355-PMDZ board, wired as a remote SPI sensor head.
- Built-in Teensy 4.1 microSD socket.
- One external RGB status LED.
- One physical Run/Stop pushbutton.
- USB device serial to a Windows computer.

## Selected Teensy pins

| Function | Teensy 4.1 pin | Direction | Notes |
| --- | ---: | --- | --- |
| ADXL355 CS | 10 | Output | Dedicated chip select. Kept high when idle. |
| ADXL355 MOSI | 11 | Output | SPI0 MOSI. |
| ADXL355 MISO | 12 | Input | SPI0 MISO. |
| ADXL355 SCLK | 13 | Output | SPI0 SCK. Also drives the Teensy orange LED; this is acceptable but can make the onboard LED flicker during SPI. Move to another SPI port if that is undesirable. |
| ADXL355 DRDY | 2 | Input interrupt | Active-high data-ready signal from ADXL355 PMOD pin 10. |
| ADXL355 INT1 | 3 | Input interrupt | Optional status interrupt from PMOD pin 7. Not required for basic logging. |
| ADXL355 INT2 | 4 | Input interrupt | Optional status interrupt from PMOD pin 9. Not required for basic logging. |
| RGB LED red | 5 | PWM output | External resistor required. |
| RGB LED green | 6 | PWM output | External resistor required. |
| RGB LED blue | 9 | PWM output | External resistor required. |
| Run/Stop button | 8 | Input pullup | Button connects pin 8 to GND when pressed. Firmware debounces. |
| microSD card | Built-in socket | SDIO | Use `SD.begin(BUILTIN_SDCARD)`. Do not wire the ADXL355 to SDIO pads. |
| USB serial | Main USB device port | USB | Virtual serial COM port. Not physical RS-232 voltage levels. |
| RTC battery | VBAT and GND | Power | Optional CR2032 or other 3 V coin cell. |

## PMOD P1 mapping for EVAL-ADXL355-PMDZ

| PMOD pin | PMOD signal | Teensy connection |
| ---: | --- | --- |
| 1 | CS | Pin 10 |
| 2 | MOSI | Pin 11 |
| 3 | MISO | Pin 12 |
| 4 | SCLK | Pin 13 |
| 5 | DGND | GND |
| 6 | VDD | 3.3 V |
| 7 | INT1 | Pin 3 |
| 8 | NC | No connection |
| 9 | INT2 | Pin 4 |
| 10 | DRDY | Pin 2 |
| 11 | DGND | GND |
| 12 | VDD | 3.3 V |

## Assumptions

- The PMOD board is powered from Teensy 3.3 V, not from 5 V.
- SPI0 pins are used because they are accessible and supported directly by the Arduino `SPI` library.
- Pin 13 is acceptable as SCLK even though it is connected to the Teensy's onboard LED. If the LED loading or flicker is problematic, move the accelerometer to a different Teensy SPI port and update `Pins.h`.
- The ADXL355 remote sensor cable is short. For longer cables, add a small buffer or place the Teensy near the sensor head.
