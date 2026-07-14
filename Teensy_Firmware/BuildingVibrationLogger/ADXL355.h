#pragma once

#include <Arduino.h>
#include <SPI.h>
#include "SampleRecord.h"

class ADXL355 {
 public:
  enum Register : uint8_t {
    REG_DEVID_AD = 0x00,
    REG_DEVID_MST = 0x01,
    REG_PARTID = 0x02,
    REG_STATUS = 0x04,
    REG_TEMP2 = 0x06,
    REG_TEMP1 = 0x07,
    REG_XDATA3 = 0x08,
    REG_FILTER = 0x28,
    REG_RANGE = 0x2C,
    REG_POWER_CTL = 0x2D,
    REG_RESET = 0x2F
  };

  static constexpr uint8_t EXPECTED_DEVID_AD = 0xAD;
  static constexpr uint8_t EXPECTED_DEVID_MST = 0x1D;
  static constexpr uint8_t EXPECTED_PARTID = 0xED;
  static constexpr float STANDARD_GRAVITY = 9.80665f;

  explicit ADXL355(uint8_t csPin);

  void begin();
  bool verifyIdentity();
  bool configure(uint8_t rangeG, uint8_t odrCode, uint8_t hpfCode);
  bool readAcceleration(AccelReading &reading, uint8_t rangeG);
  uint8_t readRegister(uint8_t reg);
  void writeRegister(uint8_t reg, uint8_t value);
  void readRegisters(uint8_t startReg, uint8_t *buffer, size_t length);

  bool isOnline() const { return online_; }
  uint8_t deviceIdAd() const { return devidAd_; }
  uint8_t deviceIdMst() const { return devidMst_; }
  uint8_t partId() const { return partId_; }

  static int32_t decodeSigned20(uint8_t byte2, uint8_t byte1, uint8_t byte0);
  static float countsPerG(uint8_t rangeG);
  static float countsToMps2(int32_t counts, uint8_t rangeG, float offsetCounts, float scale);
  static float decodeTemperatureC(uint16_t rawTemp);
  static uint8_t odrCodeForRate(uint16_t rateHz);
  static uint16_t rateForOdrCode(uint8_t odrCode);

 private:
  uint8_t csPin_;
  bool online_ = false;
  uint8_t devidAd_ = 0;
  uint8_t devidMst_ = 0;
  uint8_t partId_ = 0;
  SPISettings settings_;

  void select();
  void deselect();
};
