#pragma once

#include "driver/gpio.h"

inline void pre_enable_ds18b20_power() {
  const gpio_num_t pin = GPIO_NUM_16;
  gpio_set_direction(pin, GPIO_MODE_OUTPUT);
  gpio_set_level(pin, 1);
}
