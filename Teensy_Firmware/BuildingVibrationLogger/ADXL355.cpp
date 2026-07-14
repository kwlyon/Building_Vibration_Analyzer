#include "ADXL355.h"

namespace {
constexpr uint8_t SPI_READ = 0x01;
constexpr uint8_t POWER_STANDBY = 0x01;
constexpr uint8_t POWER_MEASURE = 0x00;
constexpr uint8_t RESET_CODE = 0x52;
}

ADXL355::ADXL355(uint8_t csPin)
    : csPin_(csPin), settings_(1000000, MSBFIRST, SPI_MODE0) {}

void ADXL355::begin() {
  pinMode(csPin_, OUTPUT);
  deselect();
  SPI.begin();
  delay(10);
  verifyIdentity();
}

bool ADXL355::verifyIdentity() {
  devidAd_ = readRegister(REG_DEVID_AD);
  devidMst_ = readRegister(REG_DEVID_MST);
  partId_ = readRegister(REG_PARTID);
  online_ = (devidAd_ == EXPECTED_DEVID_AD && devidMst_ == EXPECTED_DEVID_MST &&
             partId_ == EXPECTED_PARTID);
  return online_;
}

bool ADXL355::configure(uint8_t rangeG, uint8_t odrCode, uint8_t hpfCode) {
  if (!verifyIdentity()) {
    return false;
  }

  writeRegister(REG_POWER_CTL, POWER_STANDBY);
  delay(10);

  const uint8_t filterValue = ((hpfCode & 0x07) << 4) | (odrCode & 0x0F);
  writeRegister(REG_FILTER, filterValue);

  uint8_t rangeValue = 0x01;
  if (rangeG == 4) {
    rangeValue = 0x02;
  } else if (rangeG == 8) {
    rangeValue = 0x03;
  }
  writeRegister(REG_RANGE, rangeValue);

  writeRegister(REG_POWER_CTL, POWER_MEASURE);
  delay(10);
  return true;
}

bool ADXL355::readAcceleration(AccelReading &reading, uint8_t rangeG) {
  uint8_t data[11] = {0};
  readRegisters(REG_STATUS, data, sizeof(data));

  reading.statusFlags = data[0];
  const uint16_t tempRaw = (static_cast<uint16_t>(data[2]) << 8) | data[3];
  reading.temperatureC = decodeTemperatureC(tempRaw & 0x0FFF);

  reading.xCounts = decodeSigned20(data[4], data[5], data[6]);
  reading.yCounts = decodeSigned20(data[7], data[8], data[9]);
  readRegisters(REG_XDATA3 + 6, data, 3);
  reading.zCounts = decodeSigned20(data[0], data[1], data[2]);

  reading.xMps2 = countsToMps2(reading.xCounts, rangeG, 0.0f, 1.0f);
  reading.yMps2 = countsToMps2(reading.yCounts, rangeG, 0.0f, 1.0f);
  reading.zMps2 = countsToMps2(reading.zCounts, rangeG, 0.0f, 1.0f);
  return true;
}

uint8_t ADXL355::readRegister(uint8_t reg) {
  uint8_t value = 0;
  SPI.beginTransaction(settings_);
  select();
  SPI.transfer(static_cast<uint8_t>((reg << 1) | SPI_READ));
  value = SPI.transfer(0x00);
  deselect();
  SPI.endTransaction();
  return value;
}

void ADXL355::writeRegister(uint8_t reg, uint8_t value) {
  SPI.beginTransaction(settings_);
  select();
  SPI.transfer(static_cast<uint8_t>(reg << 1));
  SPI.transfer(value);
  deselect();
  SPI.endTransaction();
}

void ADXL355::readRegisters(uint8_t startReg, uint8_t *buffer, size_t length) {
  SPI.beginTransaction(settings_);
  select();
  SPI.transfer(static_cast<uint8_t>((startReg << 1) | SPI_READ));
  for (size_t i = 0; i < length; ++i) {
    buffer[i] = SPI.transfer(0x00);
  }
  deselect();
  SPI.endTransaction();
}

int32_t ADXL355::decodeSigned20(uint8_t byte2, uint8_t byte1, uint8_t byte0) {
  uint32_t raw = (static_cast<uint32_t>(byte2) << 12) |
                 (static_cast<uint32_t>(byte1) << 4) |
                 (static_cast<uint32_t>(byte0) >> 4);
  if (raw & 0x80000UL) {
    raw |= 0xFFF00000UL;
  }
  return static_cast<int32_t>(raw);
}

float ADXL355::countsPerG(uint8_t rangeG) {
  if (rangeG == 4) {
    return 128000.0f;
  }
  if (rangeG == 8) {
    return 64000.0f;
  }
  return 256000.0f;
}

float ADXL355::countsToMps2(int32_t counts, uint8_t rangeG, float offsetCounts, float scale) {
  const float corrected = (static_cast<float>(counts) - offsetCounts) * scale;
  return corrected / countsPerG(rangeG) * STANDARD_GRAVITY;
}

float ADXL355::decodeTemperatureC(uint16_t rawTemp) {
  return 25.0f + (1885.0f - static_cast<float>(rawTemp)) / 9.05f;
}

uint8_t ADXL355::odrCodeForRate(uint16_t rateHz) {
  if (rateHz >= 4000) return 0x00;
  if (rateHz >= 2000) return 0x01;
  if (rateHz >= 1000) return 0x02;
  if (rateHz >= 500) return 0x03;
  if (rateHz >= 250) return 0x04;
  if (rateHz >= 125) return 0x05;
  if (rateHz >= 62) return 0x06;
  if (rateHz >= 31) return 0x07;
  if (rateHz >= 15) return 0x08;
  if (rateHz >= 8) return 0x09;
  if (rateHz >= 4) return 0x0A;
  return 0x0A;
}

uint16_t ADXL355::rateForOdrCode(uint8_t odrCode) {
  static const uint16_t rates[] = {4000, 2000, 1000, 500, 250, 125, 62, 31, 15, 8, 4};
  if (odrCode < sizeof(rates) / sizeof(rates[0])) {
    return rates[odrCode];
  }
  return 4;
}

void ADXL355::select() {
  digitalWrite(csPin_, LOW);
}

void ADXL355::deselect() {
  digitalWrite(csPin_, HIGH);
}
