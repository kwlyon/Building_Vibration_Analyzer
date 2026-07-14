#include "CommandProtocol.h"
#include "Version.h"

void CommandProtocol::begin(Stream &stream, const CommandContext &context) {
  stream_ = &stream;
  ctx_ = context;
}

void CommandProtocol::poll() {
  if (!stream_) {
    return;
  }
  while (stream_->available()) {
    char c = static_cast<char>(stream_->read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      line_[lineLen_] = '\0';
      trim(line_);
      if (lineLen_ > 0 || line_[0] != '\0') {
        handleLine(line_);
      }
      lineLen_ = 0;
      line_[0] = '\0';
      continue;
    }
    if (lineLen_ + 1 < sizeof(line_)) {
      line_[lineLen_++] = c;
    } else {
      stream_->println("ERR LINE too_long");
      lineLen_ = 0;
    }
  }
}

void CommandProtocol::handleLine(char *line) {
  if (equalsIgnoreCase(line, "HELP")) {
    printHelp();
  } else if (equalsIgnoreCase(line, "STATUS")) {
    printStatus();
  } else if (equalsIgnoreCase(line, "START")) {
    if (ctx_.startLogging && ctx_.startLogging()) {
      stream_->println("OK START");
    } else {
      stream_->println("ERR START failed");
    }
  } else if (equalsIgnoreCase(line, "STOP")) {
    if (ctx_.stopLogging && ctx_.stopLogging()) {
      stream_->println("OK STOP");
    } else {
      stream_->println("ERR STOP failed");
    }
  } else if (equalsIgnoreCase(line, "GET CONFIG")) {
    printConfig();
  } else if (startsWithIgnoreCase(line, "SET RATE ")) {
    if (isRecording()) {
      stream_->println("ERR BUSY recording");
      return;
    }
    const uint16_t rate = static_cast<uint16_t>(atoi(line + 9));
    if (rate < 4 || rate > 4000) {
      stream_->println("ERR VALUE rate_out_of_range");
      return;
    }
    ctx_.config->sampleRateHz = ADXL355::rateForOdrCode(ADXL355::odrCodeForRate(rate));
    ctx_.config->odrCode = ADXL355::odrCodeForRate(rate);
    stream_->println("OK SET_RATE");
  } else if (startsWithIgnoreCase(line, "SET RANGE ")) {
    if (isRecording()) {
      stream_->println("ERR BUSY recording");
      return;
    }
    const uint8_t range = static_cast<uint8_t>(atoi(line + 10));
    if (range != 2 && range != 4 && range != 8) {
      stream_->println("ERR VALUE range_must_be_2_4_8");
      return;
    }
    ctx_.config->rangeG = range;
    stream_->println("OK SET_RANGE");
  } else if (startsWithIgnoreCase(line, "SET FILTER ")) {
    if (isRecording()) {
      stream_->println("ERR BUSY recording");
      return;
    }
    char *args = line + 11;
    ctx_.config->odrCode = static_cast<uint8_t>(strtoul(args, &args, 0)) & 0x0F;
    while (*args == ' ') ++args;
    if (*args != '\0') {
      ctx_.config->hpfCode = static_cast<uint8_t>(strtoul(args, nullptr, 0)) & 0x07;
    }
    ctx_.config->sampleRateHz = ADXL355::rateForOdrCode(ctx_.config->odrCode);
    stream_->println("OK SET_FILTER");
  } else if (startsWithIgnoreCase(line, "SET FILENAME ")) {
    if (isRecording()) {
      stream_->println("ERR BUSY recording");
      return;
    }
    ConfigManager::sanitizeFilename(line + 13, ctx_.config->filename, sizeof(ctx_.config->filename));
    stream_->print("OK SET_FILENAME name=");
    stream_->println(ctx_.config->filename);
  } else if (startsWithIgnoreCase(line, "SET RTC ")) {
    if (ctx_.clock && ctx_.clock->setFromIso8601(line + 8)) {
      stream_->println("OK SET_RTC");
    } else {
      stream_->println("ERR RTC bad_timestamp");
    }
  } else if (equalsIgnoreCase(line, "GET RTC")) {
    char ts[28];
    ctx_.clock->format(ctx_.clock->nowTime(), ctx_.clock->isValid(), ts, sizeof(ts));
    stream_->print("OK RTC valid=");
    stream_->print(ctx_.clock->isValid() ? 1 : 0);
    stream_->print(" value=");
    stream_->println(ts);
  } else if (equalsIgnoreCase(line, "LIST FILES")) {
    ctx_.logger->listFiles(*stream_);
  } else if (startsWithIgnoreCase(line, "FILE INFO ")) {
    ctx_.logger->fileInfo(line + 10, *stream_);
  } else if (startsWithIgnoreCase(line, "READ FILE ")) {
    char *name = line + 10;
    char *offsetText = strchr(name, ' ');
    uint32_t offset = 0;
    uint32_t length = 1024;
    if (offsetText) {
      *offsetText++ = '\0';
      offset = strtoul(offsetText, &offsetText, 0);
      if (offsetText && *offsetText == ' ') {
        length = strtoul(offsetText + 1, nullptr, 0);
      }
    }
    ctx_.logger->readFileChunk(name, offset, length, *stream_);
  } else if (startsWithIgnoreCase(line, "DELETE FILE ")) {
    if (isRecording()) {
      stream_->println("ERR BUSY recording");
      return;
    }
    stream_->println(ctx_.logger->deleteFile(line + 12) ? "OK DELETE" : "ERR DELETE failed");
  } else if (startsWithIgnoreCase(line, "DOWNLOAD FILE ")) {
    stream_->println("OK DOWNLOAD mode=text_chunk note=use_READ_FILE_for_chunks");
    ctx_.logger->readFileChunk(line + 14, 0, 2048, *stream_);
  } else if (equalsIgnoreCase(line, "GET ERRORS")) {
    stream_->print("OK ERRORS sd_write=");
    stream_->print(ctx_.logger->writeErrors());
    stream_->print(" dropped=");
    stream_->print(ctx_.droppedSamples ? *ctx_.droppedSamples : 0);
    stream_->print(" overruns=");
    stream_->println(ctx_.bufferOverruns ? *ctx_.bufferOverruns : 0);
  } else if (equalsIgnoreCase(line, "CLEAR ERRORS")) {
    stream_->println("OK CLEAR_ERRORS note=volatile_counters_reset_on_restart");
  } else if (equalsIgnoreCase(line, "GET SENSOR INFO")) {
    printSensorInfo();
  } else if (equalsIgnoreCase(line, "CALIBRATE OFFSET")) {
    stream_->println("OK CALIBRATE_OFFSET mode=manual_gravity_follow_user_manual");
  } else if (equalsIgnoreCase(line, "SAVE CONFIG")) {
    stream_->println(ctx_.configManager->save(*ctx_.config) ? "OK SAVE_CONFIG" : "ERR SAVE_CONFIG failed");
  } else if (equalsIgnoreCase(line, "LOAD DEFAULTS")) {
    if (isRecording()) {
      stream_->println("ERR BUSY recording");
      return;
    }
    ctx_.configManager->defaults(*ctx_.config);
    stream_->println("OK LOAD_DEFAULTS");
  } else if (equalsIgnoreCase(line, "REBOOT")) {
    stream_->println("OK REBOOT");
    delay(50);
    SCB_AIRCR = 0x05FA0004;
  } else {
    stream_->println("ERR UNKNOWN command");
  }
}

void CommandProtocol::printHelp() {
  stream_->println("OK HELP");
  stream_->println("INFO HELP STATUS START STOP GET CONFIG SET RATE <hz> SET RANGE <2|4|8>");
  stream_->println("INFO SET FILTER <odr_code> [hpf_code] SET FILENAME <name> SET RTC <iso> GET RTC");
  stream_->println("INFO LIST FILES FILE INFO <name> READ FILE <name> [offset] [length] DOWNLOAD FILE <name>");
  stream_->println("INFO DELETE FILE <name> GET ERRORS CLEAR ERRORS GET SENSOR INFO SAVE CONFIG LOAD DEFAULTS REBOOT");
}

void CommandProtocol::printStatus() {
  stream_->print("OK STATUS firmware=");
  stream_->print(BVA_FIRMWARE_VERSION);
  stream_->print(" hardware=\"");
  stream_->print(BVA_HARDWARE_NAME);
  stream_->print("\" recording=");
  stream_->print(isRecording() ? 1 : 0);
  stream_->print(" sensor=");
  stream_->print(ctx_.sensor && ctx_.sensor->isOnline() ? 1 : 0);
  stream_->print(" sd=");
  stream_->print(ctx_.logger && ctx_.logger->sdReady() ? 1 : 0);
  stream_->print(" rtc_valid=");
  stream_->print(ctx_.clock && ctx_.clock->isValid() ? 1 : 0);
  stream_->print(" rate_hz=");
  stream_->print(ctx_.config->sampleRateHz);
  stream_->print(" range_g=");
  stream_->print(ctx_.config->rangeG);
  stream_->print(" dropped=");
  stream_->print(ctx_.droppedSamples ? *ctx_.droppedSamples : 0);
  stream_->print(" overruns=");
  stream_->println(ctx_.bufferOverruns ? *ctx_.bufferOverruns : 0);
}

void CommandProtocol::printConfig() {
  stream_->print("OK CONFIG rate_hz=");
  stream_->print(ctx_.config->sampleRateHz);
  stream_->print(" range_g=");
  stream_->print(ctx_.config->rangeG);
  stream_->print(" odr_code=");
  stream_->print(ctx_.config->odrCode);
  stream_->print(" hpf_code=");
  stream_->print(ctx_.config->hpfCode);
  stream_->print(" filename=");
  stream_->print(ctx_.config->filename);
  stream_->print(" flush_ms=");
  stream_->println(static_cast<unsigned long>(ctx_.config->flushIntervalMs));
}

void CommandProtocol::printSensorInfo() {
  if (ctx_.sensor) {
    ctx_.sensor->verifyIdentity();
  }
  stream_->print("OK SENSOR online=");
  stream_->print(ctx_.sensor && ctx_.sensor->isOnline() ? 1 : 0);
  stream_->print(" devid_ad=0x");
  stream_->print(ctx_.sensor ? ctx_.sensor->deviceIdAd() : 0, HEX);
  stream_->print(" devid_mst=0x");
  stream_->print(ctx_.sensor ? ctx_.sensor->deviceIdMst() : 0, HEX);
  stream_->print(" partid=0x");
  stream_->println(ctx_.sensor ? ctx_.sensor->partId() : 0, HEX);
}

bool CommandProtocol::isRecording() const {
  return ctx_.recording && *ctx_.recording;
}

void CommandProtocol::trim(char *text) {
  char *start = text;
  while (*start == ' ' || *start == '\t') {
    ++start;
  }
  if (start != text) {
    memmove(text, start, strlen(start) + 1);
  }
  size_t len = strlen(text);
  while (len > 0 && (text[len - 1] == ' ' || text[len - 1] == '\t')) {
    text[--len] = '\0';
  }
}

bool CommandProtocol::equalsIgnoreCase(const char *a, const char *b) {
  while (*a && *b) {
    if (toupper(*a++) != toupper(*b++)) {
      return false;
    }
  }
  return *a == '\0' && *b == '\0';
}

bool CommandProtocol::startsWithIgnoreCase(const char *text, const char *prefix) {
  while (*prefix) {
    if (*text == '\0' || toupper(*text++) != toupper(*prefix++)) {
      return false;
    }
  }
  return true;
}
