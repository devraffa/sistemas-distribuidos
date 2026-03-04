#include "utils.h"

void init_tela() {
  // Inicializa o I2C
  i2c_init(I2C_PORT, 400 * 1000); // Configura I2C para 400 kHz
  gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
  gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(SDA_PIN);
  gpio_pull_up(SCL_PIN);

  // Inicializa o display OLED
  ssd1306_init(I2C_PORT);
  ssd1306_clear();
}

void init_joystick() {
  // Inicializa o ADC
  adc_init();
  adc_gpio_init(JOY_X_PIN);
  adc_gpio_init(JOY_Y_PIN);
}

void print_joystick(char *player_str, char *str_x, char *str_y, size_t buffer_size,
                    uint bar_width) {
  // Lê os valores do joystick
  adc_select_input(0);
  uint adc_y_raw = adc_read();
  adc_select_input(1);
  uint adc_x_raw = adc_read();

  // Converte os valores do joystick para caracteres
  const uint adc_max = (1 << 12) - 1;
  uint bar_x_pos = adc_x_raw * bar_width / adc_max;
  uint bar_y_pos = adc_y_raw * bar_width / adc_max;

  // Imprime os valores do joystick
  // --- Para o Eixo X ---
  int pos = snprintf(str_x, buffer_size, "X: [");
  for (uint i = 0; i < bar_width; ++i) {
    str_x[pos++] = (i == bar_x_pos) ? '*' : ' ';
  }
  str_x[pos] = '\0';
  snprintf(str_x + pos, buffer_size - pos, "]");

  // --- Para o Eixo Y ---
  pos = snprintf(str_y, buffer_size, "Y: [");
  for (uint i = 0; i < bar_width; ++i) {
    str_y[pos++] = (i == bar_y_pos) ? '*' : ' ';
  }
  str_y[pos] = '\0';
  snprintf(str_y + pos, buffer_size - pos, "]");

  // Imprime os valores do joystick
  ssd1306_clear();
  ssd1306_draw_string(get_center_x(player_str), get_center_y() - 15, player_str, true);
  ssd1306_draw_string(get_center_x(str_x), get_center_y(), str_x, true);
  ssd1306_draw_string(get_center_x(str_y), get_center_y() + 10, str_y, true);
  ssd1306_update(I2C_PORT);
}