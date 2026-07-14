#pragma once

#include <Arduino.h>
#include <TimeLib.h>

class RtcClock {
 public:
  void begin();
  bool setFromIso8601(const char *iso);
  bool isValid() const { return valid_; }
  time_t nowTime() const { return now(); }
  void format(time_t value, bool valid, char *buffer, size_t bufferSize) const;

 private:
  bool valid_ = false;
};
