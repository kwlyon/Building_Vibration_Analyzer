#pragma once

#include <Arduino.h>
#include "ADXL355.h"
#include "Config.h"
#include "RingBuffer.h"
#include "RtcClock.h"
#include "SampleRecord.h"

class Sampler {
 public:
  void begin(ADXL355 *sensor, LoggerConfig *config, RtcClock *clock,
             RingBuffer<SampleRecord, 512> *buffer, uint8_t drdyPin);
  void start(uint32_t sessionId);
  void stop();
  void service();
  bool active() const { return active_; }
  uint32_t droppedSamples() const { return droppedSamples_; }
  uint32_t sampleCount() const { return sampleNumber_; }
  uint32_t pendingEvents() const { return dataReadyEvents_; }
  static void isrThunk();

 private:
  static Sampler *instance_;
  ADXL355 *sensor_ = nullptr;
  LoggerConfig *config_ = nullptr;
  RtcClock *clock_ = nullptr;
  RingBuffer<SampleRecord, 512> *buffer_ = nullptr;
  uint8_t drdyPin_ = 0;
  volatile uint32_t dataReadyEvents_ = 0;
  bool active_ = false;
  uint32_t sessionId_ = 0;
  uint32_t startUs_ = 0;
  uint32_t sampleNumber_ = 0;
  uint32_t droppedSamples_ = 0;

  void onDataReady();
};
