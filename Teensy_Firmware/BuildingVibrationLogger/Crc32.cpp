#include "Crc32.h"

uint32_t crc32_update(uint32_t crc, const uint8_t *data, size_t length) {
  crc = ~crc;
  for (size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      const uint32_t mask = -(crc & 1U);
      crc = (crc >> 1) ^ (0xEDB88320UL & mask);
    }
  }
  return ~crc;
}

uint32_t crc32_compute(const uint8_t *data, size_t length) {
  return crc32_update(0, data, length);
}
