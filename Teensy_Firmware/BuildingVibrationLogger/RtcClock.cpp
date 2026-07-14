#include "RtcClock.h"

namespace {
time_t getTeensyRtc() {
  return Teensy3Clock.get();
}

bool parseTwo(const char *s, uint8_t &value) {
  if (!isdigit(s[0]) || !isdigit(s[1])) {
    return false;
  }
  value = static_cast<uint8_t>((s[0] - '0') * 10 + (s[1] - '0'));
  return true;
}

bool parseFour(const char *s, uint16_t &value) {
  for (uint8_t i = 0; i < 4; ++i) {
    if (!isdigit(s[i])) {
      return false;
    }
  }
  value = static_cast<uint16_t>((s[0] - '0') * 1000 + (s[1] - '0') * 100 +
                                (s[2] - '0') * 10 + (s[3] - '0'));
  return true;
}
}

void RtcClock::begin() {
  setSyncProvider(getTeensyRtc);
  const time_t t = now();
  valid_ = year(t) >= 2024 && year(t) <= 2099;
}

bool RtcClock::setFromIso8601(const char *iso) {
  if (strlen(iso) < 19 || iso[4] != '-' || iso[7] != '-' || iso[10] != 'T' ||
      iso[13] != ':' || iso[16] != ':') {
    return false;
  }

  uint16_t yr;
  uint8_t mon;
  uint8_t dayValue;
  uint8_t hr;
  uint8_t minValue;
  uint8_t sec;
  if (!parseFour(iso, yr) || !parseTwo(iso + 5, mon) || !parseTwo(iso + 8, dayValue) ||
      !parseTwo(iso + 11, hr) || !parseTwo(iso + 14, minValue) || !parseTwo(iso + 17, sec)) {
    return false;
  }
  if (yr < 2024 || yr > 2099 || mon < 1 || mon > 12 || dayValue < 1 || dayValue > 31 ||
      hr > 23 || minValue > 59 || sec > 59) {
    return false;
  }

  TimeElements tm;
  tm.Year = CalendarYrToTm(yr);
  tm.Month = mon;
  tm.Day = dayValue;
  tm.Hour = hr;
  tm.Minute = minValue;
  tm.Second = sec;
  tm.Wday = 0;
  const time_t t = makeTime(tm);
  Teensy3Clock.set(t);
  setTime(t);
  valid_ = true;
  return true;
}

void RtcClock::format(time_t value, bool valid, char *buffer, size_t bufferSize) const {
  if (!valid || value == 0) {
    strncpy(buffer, "RTC_INVALID", bufferSize);
    buffer[bufferSize - 1] = '\0';
    return;
  }
  snprintf(buffer, bufferSize, "%04d-%02d-%02dT%02d:%02d:%02dZ",
           year(value), month(value), day(value), hour(value), minute(value), second(value));
}
