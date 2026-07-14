#pragma once

#include <Arduino.h>

uint32_t crc32_update(uint32_t crc, const uint8_t *data, size_t length);
uint32_t crc32_compute(const uint8_t *data, size_t length);
