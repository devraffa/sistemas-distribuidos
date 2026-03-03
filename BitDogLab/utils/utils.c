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

int connect_wifi() {
  if (cyw43_arch_init()) {
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("Erro ao iniciar Wi-Fi"), get_center_y() - 5, "Erro ao iniciar Wi-Fi", true);
    ssd1306_update(I2C_PORT);
    return 0;
  }

  cyw43_arch_enable_sta_mode();

  const char *ssid = "rede-teste"; // SEU_WIFI
  const char *password = "Rteste-314"; // SUA_SENHA

  ssd1306_clear();
  ssd1306_draw_string(get_center_x("Conectando Wi-Fi..."), get_center_y() - 5, "Conectando Wi-Fi...", true);
  ssd1306_draw_string(get_center_x(ssid), get_center_y() + 5, ssid, true);
  ssd1306_update(I2C_PORT);

  if (cyw43_arch_wifi_connect_timeout_ms(ssid, password,
          CYW43_AUTH_WPA2_AES_PSK, 30000)) {
      ssd1306_clear();
      ssd1306_draw_string(get_center_x("Falha ao conectar"), get_center_y() - 5, "Falha ao conectar", true);
      ssd1306_update(I2C_PORT);
  } else {
      ssd1306_clear();
      ssd1306_draw_string(get_center_x("Conectado!"), get_center_y() - 5, "Conectado!", true);
      ssd1306_update(I2C_PORT);
  }
  sleep_ms(5000);
  return 1;
  }

void print_joystick(char *str_x, char *str_y, size_t buffer_size, uint bar_width) {
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
  ssd1306_draw_string(get_center_x(str_x), get_center_y() - 5, str_x, true);
  ssd1306_draw_string(get_center_x(str_y), get_center_y() + 5, str_y, true);
  ssd1306_update(I2C_PORT);
}