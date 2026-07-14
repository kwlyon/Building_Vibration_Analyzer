#pragma once

#include <Arduino.h>

namespace Pins {
constexpr uint8_t ADXL355_CS = 10;
constexpr uint8_t ADXL355_MOSI = 11;
constexpr uint8_t ADXL355_MISO = 12;
constexpr uint8_t ADXL355_SCLK = 13;
constexpr uint8_t ADXL355_DRDY = 2;
constexpr uint8_t ADXL355_INT1 = 3;
constexpr uint8_t ADXL355_INT2 = 4;

constexpr uint8_t LED_RED = 5;
constexpr uint8_t LED_GREEN = 6;
constexpr uint8_t LED_BLUE = 9;
constexpr uint8_t RUN_STOP_BUTTON = 8;
}

#ifndef LED_COMMON_ANODE
#define LED_COMMON_ANODE 0
#endif
