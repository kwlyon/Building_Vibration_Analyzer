#pragma once

#include <Arduino.h>

enum class LedState : uint8_t {
  Off,
  Idle,
  Recording,
  Warning,
  Fault,
  FaultBlink,
  Host
};

class StatusLed {
 public:
  StatusLed(uint8_t redPin, uint8_t greenPin, uint8_t bluePin);
  void begin(bool commonAnode);
  void setState(LedState state);
  void update();
  LedState state() const { return state_; }

 private:
  uint8_t redPin_;
  uint8_t greenPin_;
  uint8_t bluePin_;
  bool commonAnode_ = false;
  LedState state_ = LedState::Off;
  uint32_t lastUpdateMs_ = 0;
  bool blinkOn_ = false;

  void writeRgb(uint8_t r, uint8_t g, uint8_t b);
};
