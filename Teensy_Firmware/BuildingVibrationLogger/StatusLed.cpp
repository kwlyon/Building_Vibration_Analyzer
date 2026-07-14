#include "StatusLed.h"

StatusLed::StatusLed(uint8_t redPin, uint8_t greenPin, uint8_t bluePin)
    : redPin_(redPin), greenPin_(greenPin), bluePin_(bluePin) {}

void StatusLed::begin(bool commonAnode) {
  commonAnode_ = commonAnode;
  pinMode(redPin_, OUTPUT);
  pinMode(greenPin_, OUTPUT);
  pinMode(bluePin_, OUTPUT);
  setState(LedState::Idle);
}

void StatusLed::setState(LedState state) {
  state_ = state;
  lastUpdateMs_ = 0;
  blinkOn_ = false;
  update();
}

void StatusLed::update() {
  const uint32_t nowMs = millis();
  switch (state_) {
    case LedState::Off:
      writeRgb(0, 0, 0);
      break;
    case LedState::Idle:
      writeRgb(0, 0, 80);
      break;
    case LedState::Recording: {
      const uint8_t level = 40 + static_cast<uint8_t>((nowMs / 16) % 80);
      writeRgb(0, level, 0);
      break;
    }
    case LedState::Warning:
      writeRgb(90, 50, 0);
      break;
    case LedState::Fault:
      writeRgb(120, 0, 0);
      break;
    case LedState::FaultBlink:
      if (nowMs - lastUpdateMs_ >= 250) {
        lastUpdateMs_ = nowMs;
        blinkOn_ = !blinkOn_;
      }
      writeRgb(blinkOn_ ? 120 : 0, 0, 0);
      break;
    case LedState::Host:
      writeRgb(50, 0, 80);
      break;
  }
}

void StatusLed::writeRgb(uint8_t r, uint8_t g, uint8_t b) {
  if (commonAnode_) {
    r = 255 - r;
    g = 255 - g;
    b = 255 - b;
  }
  analogWrite(redPin_, r);
  analogWrite(greenPin_, g);
  analogWrite(bluePin_, b);
}
