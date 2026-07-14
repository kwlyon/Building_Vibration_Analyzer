#pragma once

#include <Arduino.h>

class Button {
 public:
  explicit Button(uint8_t pin);
  void begin();
  bool pressedEvent();

 private:
  uint8_t pin_;
  bool stableState_ = HIGH;
  bool lastReading_ = HIGH;
  uint32_t lastChangeMs_ = 0;
  uint32_t lastEventMs_ = 0;
};
