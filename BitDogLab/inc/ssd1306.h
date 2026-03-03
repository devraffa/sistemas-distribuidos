#ifndef SSD1306_H
#define SSD1306_H

#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include <string.h> // Para memcpy e memset

// Definições para o display SSD1306
#define SSD1306_I2C_ADDR 0x3C
#define SSD1306_WIDTH 128
#define SSD1306_HEIGHT 64

// Prototipação das funções
void ssd1306_init(i2c_inst_t *i2c);
void ssd1306_clear();
void ssd1306_update(i2c_inst_t *i2c);
int get_center_x(const char *str);
int get_center_y();
void ssd1306_draw_pixel(int x, int y, bool color);
void ssd1306_draw_char(int x, int y, char c, bool color);
void ssd1306_draw_string(int x, int y, const char *str, bool color);

#endif // SSD1306_H