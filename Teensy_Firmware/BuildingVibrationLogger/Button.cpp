#include "Button.h"

namespace {
constexpr uint32_t DEBOUNCE_MS = 40;
constexpr uint32_t MIN_EVENT_SPACING_MS = 500;
}

Button::Button(uint8_t pin) : pin_(pin) {}

void Button::begin() {
  pinMode(pin_, INPUT_PULLUP);
  stableState_ = digitalRead(pin_);
  lastReading_ = stableState_;
}

bool Button::pressedEvent() {
  const bool reading = digitalRead(pin_);
  const uint32_t nowMs = millis();
  if (reading != lastReading_) {
    lastReading_ = reading;
    lastChangeMs_ = nowMs;
  }
  if ((nowMs - lastChangeMs_) >= DEBOUNCE_MS && reading != stableState_) {
    stableState_ = reading;
    if (stableState_ == LOW && (nowMs - lastEventMs_) >= MIN_EVENT_SPACING_MS) {
      lastEventMs_ = nowMs;
      return true;
    }
  }
  return false;
}
