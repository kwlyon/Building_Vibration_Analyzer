#pragma once

#include <Arduino.h>
#include <SD.h>
#include "Config.h"
#include "SampleRecord.h"

class CsvLogger {
 public:
  bool begin();
  bool sdReady() const { return sdReady_; }
  bool isOpen() const { return fileOpen_; }
  const char *activeFilename() const { return activeFilename_; }
  bool startSession(const LoggerConfig &config, uint32_t sessionId, bool rtcValid);
  bool appendSample(const SampleRecord &record);
  bool writeEvent(const char *recordType, uint32_t sessionId, const char *message);
  bool endSession(uint32_t sessionId, uint32_t samples, uint32_t dropped, uint32_t overruns);
  void flushIfDue(uint32_t intervalMs);
  void close();
  uint32_t writeErrors() const { return writeErrors_; }
  uint32_t bytesWritten() const { return bytesWritten_; }

  void listFiles(Print &out);
  bool fileInfo(const char *name, Print &out);
  bool readFileChunk(const char *name, uint32_t offset, uint32_t length, Print &out);
  bool deleteFile(const char *name);
  static bool isValidFilename(const char *name);

 private:
  bool sdReady_ = false;
  bool fileOpen_ = false;
  File logFile_;
  uint32_t writeErrors_ = 0;
  uint32_t bytesWritten_ = 0;
  uint32_t lastFlushMs_ = 0;
  char activeFilename_[32] = {0};

  bool writeLine(const char *line);
  bool chooseNextDataFilename(char *buffer, size_t bufferSize);
  void writeHeaderIfNeeded(bool newFile);
  void timestampForRecord(const SampleRecord &record, char *buffer, size_t bufferSize);
};
