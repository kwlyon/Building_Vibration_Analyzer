#pragma once

#include <Arduino.h>
#include "ADXL355.h"
#include "Config.h"
#include "CsvLogger.h"
#include "RtcClock.h"

struct CommandContext {
  LoggerConfig *config = nullptr;
  ConfigManager *configManager = nullptr;
  ADXL355 *sensor = nullptr;
  CsvLogger *logger = nullptr;
  RtcClock *clock = nullptr;
  bool *recording = nullptr;
  uint32_t *droppedSamples = nullptr;
  uint32_t *bufferOverruns = nullptr;
  bool (*startLogging)() = nullptr;
  bool (*stopLogging)() = nullptr;
};

class CommandProtocol {
 public:
  void begin(Stream &stream, const CommandContext &context);
  void poll();

 private:
  Stream *stream_ = nullptr;
  CommandContext ctx_;
  char line_[160] = {0};
  size_t lineLen_ = 0;

  void handleLine(char *line);
  void printHelp();
  void printStatus();
  void printConfig();
  void printSensorInfo();
  bool isRecording() const;
  void trim(char *text);
  static bool equalsIgnoreCase(const char *a, const char *b);
  static bool startsWithIgnoreCase(const char *text, const char *prefix);
};
