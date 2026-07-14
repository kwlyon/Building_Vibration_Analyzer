#pragma once

#include <Arduino.h>
#include <TimeLib.h>

struct AccelReading {
  int32_t xCounts = 0;
  int32_t yCounts = 0;
  int32_t zCounts = 0;
  float xMps2 = 0.0f;
  float yMps2 = 0.0f;
  float zMps2 = 0.0f;
  float temperatureC = NAN;
  uint32_t statusFlags = 0;
};

struct SampleRecord {
  uint32_t sessionId = 0;
  uint32_t elapsedUs = 0;
  uint32_t sampleNumber = 0;
  int32_t xCounts = 0;
  int32_t yCounts = 0;
  int32_t zCounts = 0;
  float xMps2 = 0.0f;
  float yMps2 = 0.0f;
  float zMps2 = 0.0f;
  float temperatureC = NAN;
  uint32_t statusFlags = 0;
  time_t wallTime = 0;
  bool rtcValid = false;
};
