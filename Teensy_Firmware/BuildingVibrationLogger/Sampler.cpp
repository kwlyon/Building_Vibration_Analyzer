#include "Sampler.h"

Sampler *Sampler::instance_ = nullptr;

void Sampler::begin(ADXL355 *sensor, LoggerConfig *config, RtcClock *clock,
                    RingBuffer<SampleRecord, 512> *buffer, uint8_t drdyPin) {
  sensor_ = sensor;
  config_ = config;
  clock_ = clock;
  buffer_ = buffer;
  drdyPin_ = drdyPin;
  pinMode(drdyPin_, INPUT);
  instance_ = this;
}

void Sampler::start(uint32_t sessionId) {
  dataReadyEvents_ = 0;
  droppedSamples_ = 0;
  sampleNumber_ = 0;
  sessionId_ = sessionId;
  startUs_ = micros();
  active_ = true;
  attachInterrupt(digitalPinToInterrupt(drdyPin_), Sampler::isrThunk, RISING);
}

void Sampler::stop() {
  detachInterrupt(digitalPinToInterrupt(drdyPin_));
  active_ = false;
}

void Sampler::service() {
  if (!active_ || sensor_ == nullptr || buffer_ == nullptr || config_ == nullptr) {
    return;
  }

  uint8_t serviced = 0;
  while (dataReadyEvents_ > 0 && serviced < 8) {
    noInterrupts();
    if (dataReadyEvents_ > 0) {
      --dataReadyEvents_;
    }
    interrupts();

    AccelReading reading;
    if (!sensor_->readAcceleration(reading, config_->rangeG)) {
      ++droppedSamples_;
      continue;
    }

    reading.xMps2 = ADXL355::countsToMps2(reading.xCounts, config_->rangeG,
                                          config_->offsetCounts[0], config_->scaleFactors[0]);
    reading.yMps2 = ADXL355::countsToMps2(reading.yCounts, config_->rangeG,
                                          config_->offsetCounts[1], config_->scaleFactors[1]);
    reading.zMps2 = ADXL355::countsToMps2(reading.zCounts, config_->rangeG,
                                          config_->offsetCounts[2], config_->scaleFactors[2]);

    SampleRecord record;
    record.sessionId = sessionId_;
    record.elapsedUs = micros() - startUs_;
    record.sampleNumber = sampleNumber_++;
    record.xCounts = reading.xCounts;
    record.yCounts = reading.yCounts;
    record.zCounts = reading.zCounts;
    record.xMps2 = reading.xMps2;
    record.yMps2 = reading.yMps2;
    record.zMps2 = reading.zMps2;
    record.temperatureC = reading.temperatureC;
    record.statusFlags = reading.statusFlags;
    record.wallTime = clock_ ? clock_->nowTime() : 0;
    record.rtcValid = clock_ ? clock_->isValid() : false;

    if (!buffer_->push(record)) {
      ++droppedSamples_;
    }
    ++serviced;
  }
}

void Sampler::isrThunk() {
  if (instance_) {
    instance_->onDataReady();
  }
}

void Sampler::onDataReady() {
  ++dataReadyEvents_;
}
