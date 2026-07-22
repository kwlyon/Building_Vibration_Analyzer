#include <Arduino.h>
#include "ADXL355.h"
#include "Button.h"
#include "CommandProtocol.h"
#include "Config.h"
#include "CsvLogger.h"
#include "Pins.h"
#include "RingBuffer.h"
#include "RtcClock.h"
#include "Sampler.h"
#include "StatusLed.h"
#include "Version.h"

ConfigManager configManager;
LoggerConfig config;
ADXL355 sensor(Pins::ADXL355_CS);
RtcClock rtcClock;
StatusLed statusLed(Pins::LED_RED, Pins::LED_GREEN, Pins::LED_BLUE);
Button runStopButton(Pins::RUN_STOP_BUTTON);
CsvLogger csvLogger;
RingBuffer<SampleRecord, 512> sampleBuffer;
Sampler sampler;
CommandProtocol commandProtocol;

bool recording = false;
uint32_t sessionId = 0;
uint32_t droppedSamplesSnapshot = 0;
uint32_t lastBufferOverruns = 0;

bool startLogging();
bool stopLogging();
void drainSamples();
void reportStartup();

void setup() {
  Serial.begin(115200);
  delay(200);

  configManager.load(config);
  statusLed.begin(config.ledCommonAnode != 0);
  runStopButton.begin();
  rtcClock.begin();

  sensor.begin();
  if (sensor.isOnline()) {
    sensor.configure(config.rangeG, config.odrCode, config.hpfCode);
  }

  csvLogger.begin();
  sampler.begin(&sensor, &config, &rtcClock, &sampleBuffer, Pins::ADXL355_DRDY);

  CommandContext ctx;
  ctx.config = &config;
  ctx.configManager = &configManager;
  ctx.sensor = &sensor;
  ctx.logger = &csvLogger;
  ctx.clock = &rtcClock;
  ctx.recording = &recording;
  ctx.droppedSamples = &droppedSamplesSnapshot;
  ctx.bufferOverruns = &lastBufferOverruns;
  ctx.startLogging = startLogging;
  ctx.stopLogging = stopLogging;
  commandProtocol.begin(Serial, ctx);

  reportStartup();
  statusLed.setState((sensor.isOnline() && csvLogger.sdReady()) ? LedState::Idle : LedState::Warning);
}

void loop() {
  commandProtocol.poll();

  if (runStopButton.pressedEvent()) {
    if (recording) {
      stopLogging();
      Serial.println("EVT BUTTON action=stop");
    } else {
      startLogging();
      Serial.println("EVT BUTTON action=start");
    }
  }

  sampler.service();
  drainSamples();
  csvLogger.flushIfDue(config.flushIntervalMs);

  lastBufferOverruns = sampleBuffer.overruns();
  droppedSamplesSnapshot = sampler.droppedSamples();
  if (recording && (sampler.droppedSamples() > 0 || sampleBuffer.overruns() > 0 || csvLogger.writeErrors() > 0)) {
    statusLed.setState(LedState::FaultBlink);
  }
  statusLed.update();
}

bool startLogging() {
  if (recording) {
    return true;
  }
  if (!sensor.verifyIdentity()) {
    statusLed.setState(LedState::Fault);
    Serial.println("ERR START sensor_not_found");
    return false;
  }
  if (!sensor.configure(config.rangeG, config.odrCode, config.hpfCode)) {
    statusLed.setState(LedState::Fault);
    Serial.println("ERR START sensor_config_failed");
    return false;
  }
  if (!csvLogger.sdReady() && !csvLogger.begin()) {
    statusLed.setState(LedState::Fault);
    Serial.println("ERR START sd_not_ready");
    return false;
  }

  ++sessionId;
  sampleBuffer.clear();
  if (!csvLogger.startSession(config, sessionId, rtcClock.isValid())) {
    statusLed.setState(LedState::Fault);
    Serial.println("ERR START file_open_failed");
    return false;
  }
  sampler.start(sessionId);
  recording = true;
  statusLed.setState(LedState::Recording);
  Serial.print("EVT SESSION_START id=");
  Serial.print(static_cast<unsigned long>(sessionId));
  Serial.print(" name=");
  Serial.println(csvLogger.activeFilename());
  return true;
}

bool stopLogging() {
  if (!recording) {
    return true;
  }
  sampler.stop();
  drainSamples();
  csvLogger.endSession(sessionId, sampler.sampleCount(), sampler.droppedSamples(), sampleBuffer.overruns());
  recording = false;
  statusLed.setState(LedState::Idle);
  Serial.print("EVT SESSION_END id=");
  Serial.print(static_cast<unsigned long>(sessionId));
  Serial.print(" name=");
  Serial.println(csvLogger.activeFilename());
  return true;
}

void drainSamples() {
  SampleRecord record;
  uint16_t drained = 0;
  while (sampleBuffer.pop(record) && drained < 32) {
    if (!csvLogger.appendSample(record)) {
      statusLed.setState(LedState::FaultBlink);
      break;
    }
    ++drained;
  }
}

void reportStartup() {
  Serial.print("INFO firmware=");
  Serial.print(BVA_FIRMWARE_VERSION);
  Serial.print(" hardware=\"");
  Serial.print(BVA_HARDWARE_NAME);
  Serial.println("\"");
  Serial.print("INFO sensor=");
  Serial.print(sensor.isOnline() ? "ok" : "missing");
  Serial.print(" sd=");
  Serial.print(csvLogger.sdReady() ? "ok" : "missing");
  Serial.print(" rtc_valid=");
  Serial.println(rtcClock.isValid() ? 1 : 0);
}
