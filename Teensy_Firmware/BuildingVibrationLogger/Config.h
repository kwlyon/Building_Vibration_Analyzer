#pragma once

#include <Arduino.h>
#include "Pins.h"

struct LoggerConfig {
  uint32_t magic = 0x42564131UL;
  uint16_t version = 1;
  uint16_t size = 0;
  uint32_t crc32 = 0;
  uint16_t sampleRateHz = 500;
  uint8_t rangeG = 2;
  uint8_t odrCode = 3;
  uint8_t hpfCode = 0;
  uint8_t axisMask = 0x07;
  uint8_t ledCommonAnode = LED_COMMON_ANODE ? 1 : 0;
  uint32_t flushIntervalMs = 1000;
  float offsetCounts[3] = {0.0f, 0.0f, 0.0f};
  float scaleFactors[3] = {1.0f, 1.0f, 1.0f};
  char filename[32] = "VIBRATION_DATA.CSV";
};

class ConfigManager {
 public:
  bool load(LoggerConfig &config);
  bool save(LoggerConfig &config);
  void defaults(LoggerConfig &config);
  bool validate(const LoggerConfig &config) const;
  static void sanitizeFilename(const char *input, char *output, size_t outputSize);

 private:
  uint32_t computeCrc(LoggerConfig config) const;
};
