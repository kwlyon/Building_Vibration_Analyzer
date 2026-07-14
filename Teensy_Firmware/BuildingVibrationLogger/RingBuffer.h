#pragma once

#include <Arduino.h>

template <typename T, size_t Capacity>
class RingBuffer {
 public:
  bool push(const T &value) {
    const size_t next = (head_ + 1) % Capacity;
    if (next == tail_) {
      ++overruns_;
      return false;
    }
    data_[head_] = value;
    head_ = next;
    return true;
  }

  bool pop(T &value) {
    if (empty()) {
      return false;
    }
    value = data_[tail_];
    tail_ = (tail_ + 1) % Capacity;
    return true;
  }

  bool empty() const {
    return head_ == tail_;
  }

  size_t size() const {
    if (head_ >= tail_) {
      return head_ - tail_;
    }
    return Capacity - tail_ + head_;
  }

  size_t capacity() const {
    return Capacity - 1;
  }

  uint32_t overruns() const {
    return overruns_;
  }

  void clear() {
    head_ = 0;
    tail_ = 0;
    overruns_ = 0;
  }

 private:
  T data_[Capacity];
  volatile size_t head_ = 0;
  volatile size_t tail_ = 0;
  uint32_t overruns_ = 0;
};
