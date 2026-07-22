#include "Config.h"
#include <EEPROM.h>
#include "ADXL355.h"
#include "Crc32.h"

namespace {
constexpr int EEPROM_CONFIG_ADDR = 0;
}

bool ConfigManager::load(LoggerConfig &config) {
  LoggerConfig stored;
  EEPROM.get(EEPROM_CONFIG_ADDR, stored);
  if (!validate(stored)) {
    defaults(config);
    return false;
  }
  config = stored;
  return true;
}

bool ConfigManager::save(LoggerConfig &config) {
  config.magic = 0x42564131UL;
  config.version = 1;
  config.size = sizeof(LoggerConfig);
  config.crc32 = computeCrc(config);
  EEPROM.put(EEPROM_CONFIG_ADDR, config);
  return true;
}

void ConfigManager::defaults(LoggerConfig &config) {
  config = LoggerConfig();
  config.magic = 0x42564131UL;
  config.version = 1;
  config.size = sizeof(LoggerConfig);
  config.odrCode = ADXL355::odrCodeForRate(config.sampleRateHz);
}

bool ConfigManager::validate(const LoggerConfig &config) const {
  if (config.magic != 0x42564131UL || config.version != 1 || config.size != sizeof(LoggerConfig)) {
    return false;
  }
  if (config.rangeG != 2 && config.rangeG != 4 && config.rangeG != 8) {
    return false;
  }
  if (config.odrCode > 0x0A || config.hpfCode > 0x07 || config.filename[0] == '\0') {
    return false;
  }
  return computeCrc(config) == config.crc32;
}

void ConfigManager::sanitizeFilename(const char *input, char *output, size_t outputSize) {
  if (outputSize == 0) {
    return;
  }
  size_t out = 0;
  for (size_t i = 0; input[i] != '\0' && out + 1 < outputSize; ++i) {
    const char c = input[i];
    const bool ok = isalnum(c) || c == '_' || c == '-' || c == '.';
    output[out++] = ok ? c : '_';
  }
  output[out] = '\0';
  if (out == 0) {
    strncpy(output, "Data_0.csv", outputSize);
    output[outputSize - 1] = '\0';
  }
}

uint32_t ConfigManager::computeCrc(LoggerConfig config) const {
  config.crc32 = 0;
  return crc32_compute(reinterpret_cast<const uint8_t *>(&config), sizeof(config));
}
