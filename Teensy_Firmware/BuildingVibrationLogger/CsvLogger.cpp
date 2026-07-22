#include "CsvLogger.h"
#include <TimeLib.h>

bool CsvLogger::begin() {
  sdReady_ = SD.begin(BUILTIN_SDCARD);
  return sdReady_;
}

bool CsvLogger::startSession(const LoggerConfig &config, uint32_t sessionId, bool rtcValid) {
  if (!sdReady_ && !begin()) {
    ++writeErrors_;
    return false;
  }

  const bool newFile = !SD.exists(config.filename);
  logFile_ = SD.open(config.filename, FILE_WRITE);
  if (!logFile_) {
    ++writeErrors_;
    fileOpen_ = false;
    return false;
  }
  fileOpen_ = true;
  writeHeaderIfNeeded(newFile || logFile_.size() == 0);

  char line[220];
  snprintf(line, sizeof(line),
           "SESSION_START,%lu,%s,0,0,,,,,,,,rate_hz=%u;range_g=%u;odr_code=%u;hpf_code=%u;rtc_valid=%u",
           static_cast<unsigned long>(sessionId), rtcValid ? "RTC_SET" : "RTC_INVALID",
           config.sampleRateHz, config.rangeG, config.odrCode, config.hpfCode, rtcValid ? 1 : 0);
  return writeLine(line);
}

bool CsvLogger::appendSample(const SampleRecord &record) {
  if (!fileOpen_) {
    ++writeErrors_;
    return false;
  }
  char ts[28];
  timestampForRecord(record, ts, sizeof(ts));
  char line[240];
  snprintf(line, sizeof(line),
           "DATA,%lu,%s,%lu,%lu,%ld,%ld,%ld,%.7g,%.7g,%.7g,%.3f,0x%08lX",
           static_cast<unsigned long>(record.sessionId), ts,
           static_cast<unsigned long>(record.elapsedUs),
           static_cast<unsigned long>(record.sampleNumber),
           static_cast<long>(record.xCounts), static_cast<long>(record.yCounts),
           static_cast<long>(record.zCounts),
           static_cast<double>(record.xMps2), static_cast<double>(record.yMps2),
           static_cast<double>(record.zMps2), static_cast<double>(record.temperatureC),
           static_cast<unsigned long>(record.statusFlags));
  return writeLine(line);
}

bool CsvLogger::writeEvent(const char *recordType, uint32_t sessionId, const char *message) {
  char line[180];
  snprintf(line, sizeof(line), "%s,%lu,RTC_INVALID,0,0,,,,,,,,%s",
           recordType, static_cast<unsigned long>(sessionId), message);
  return writeLine(line);
}

bool CsvLogger::endSession(uint32_t sessionId, uint32_t samples, uint32_t dropped, uint32_t overruns) {
  char line[180];
  snprintf(line, sizeof(line),
           "SESSION_END,%lu,RTC_INVALID,0,%lu,,,,,,,,samples=%lu;dropped=%lu;overruns=%lu",
           static_cast<unsigned long>(sessionId), static_cast<unsigned long>(samples),
           static_cast<unsigned long>(samples), static_cast<unsigned long>(dropped),
           static_cast<unsigned long>(overruns));
  const bool ok = writeLine(line);
  close();
  return ok;
}

void CsvLogger::flushIfDue(uint32_t intervalMs) {
  if (fileOpen_ && (millis() - lastFlushMs_) >= intervalMs) {
    logFile_.flush();
    lastFlushMs_ = millis();
  }
}

void CsvLogger::close() {
  if (fileOpen_) {
    logFile_.flush();
    logFile_.close();
  }
  fileOpen_ = false;
}

void CsvLogger::listFiles(Print &out) {
  if (!sdReady_ && !begin()) {
    out.println("ERR SD not_ready");
    return;
  }
  File root = SD.open("/");
  if (!root) {
    out.println("ERR SD root_open_failed");
    return;
  }
  out.println("OK LIST");
  File entry = root.openNextFile();
  while (entry) {
    out.print("FILE name=");
    out.print(entry.name());
    out.print(" size=");
    out.println(static_cast<unsigned long>(entry.size()));
    entry.close();
    entry = root.openNextFile();
  }
  root.close();
  out.println("END LIST");
}

bool CsvLogger::fileInfo(const char *name, Print &out) {
  if (!sdReady_ && !begin()) {
    out.println("ERR SD not_ready");
    return false;
  }
  File file = SD.open(name, FILE_READ);
  if (!file) {
    out.println("ERR FILE not_found");
    return false;
  }
  out.print("OK FILE_INFO name=");
  out.print(name);
  out.print(" size=");
  out.println(static_cast<unsigned long>(file.size()));
  file.close();
  return true;
}

bool CsvLogger::readFileChunk(const char *name, uint32_t offset, uint32_t length, Print &out) {
  if (!sdReady_ && !begin()) {
    out.println("ERR SD not_ready");
    return false;
  }
  File file = SD.open(name, FILE_READ);
  if (!file) {
    out.println("ERR FILE not_found");
    return false;
  }
  if (!file.seek(offset)) {
    out.println("ERR FILE bad_offset");
    file.close();
    return false;
  }
  const uint32_t fileSize = file.size();
  const uint32_t available = offset < fileSize ? fileSize - offset : 0;
  const uint32_t payloadLength = length < available ? length : available;
  out.print("OK READ name=");
  out.print(name);
  out.print(" offset=");
  out.print(static_cast<unsigned long>(offset));
  out.print(" length=");
  out.print(static_cast<unsigned long>(length));
  out.print(" bytes=");
  out.println(static_cast<unsigned long>(payloadLength));
  for (uint32_t i = 0; i < payloadLength; ++i) {
    out.write(static_cast<uint8_t>(file.read()));
  }
  out.println();
  out.println("END READ");
  file.close();
  return true;
}

bool CsvLogger::deleteFile(const char *name) {
  if (!sdReady_ && !begin()) {
    return false;
  }
  return SD.remove(name);
}

bool CsvLogger::writeLine(const char *line) {
  if (!fileOpen_) {
    ++writeErrors_;
    return false;
  }
  const size_t before = logFile_.size();
  logFile_.println(line);
  const size_t after = logFile_.size();
  if (after <= before) {
    ++writeErrors_;
    return false;
  }
  bytesWritten_ += static_cast<uint32_t>(after - before);
  return true;
}

void CsvLogger::writeHeaderIfNeeded(bool newFile) {
  if (!newFile) {
    return;
  }
  writeLine("record_type,session_id,timestamp_iso8601,elapsed_us,sample_number,x_counts,y_counts,z_counts,x_mps2,y_mps2,z_mps2,temperature_c,status_flags");
}

void CsvLogger::timestampForRecord(const SampleRecord &record, char *buffer, size_t bufferSize) {
  if (!record.rtcValid || record.wallTime == 0) {
    strncpy(buffer, "RTC_INVALID", bufferSize);
    buffer[bufferSize - 1] = '\0';
    return;
  }
  snprintf(buffer, bufferSize, "%04d-%02d-%02dT%02d:%02d:%02dZ",
           year(record.wallTime), month(record.wallTime), day(record.wallTime),
           hour(record.wallTime), minute(record.wallTime), second(record.wallTime));
}
