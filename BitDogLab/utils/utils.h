#ifndef UTILS_H
#define UTILS_H

#include "hardware/adc.h"
#include "hardware/i2c.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include <stdio.h>
#include <stdlib.h>

// pasta INC
#include "../inc/ssd1306.h"

// OLED
#define I2C_PORT i2c1 // i2c1 é utilizado por padrão na placa
#define SDA_PIN 14
#define SCL_PIN 15

// Joystick
#define JOY_X_PIN 26
#define JOY_Y_PIN 27

void init_tela();
void init_joystick();
int connect_wifi();
void print_joystick(char *str_x, char *str_y, size_t buffer_size,
                    uint bar_width);

#endif // UTILS_H
