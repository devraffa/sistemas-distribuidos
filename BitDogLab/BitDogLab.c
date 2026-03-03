#include <stdio.h>
#include <stdlib.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "pico/cyw43_arch.h"

// pasta INC
#include "inc/ssd1306.h"

// OLED
#define I2C_PORT i2c1 // i2c1 é utilizado por padrão na placa
#define SDA_PIN 14
#define SCL_PIN 15

int main() {
  stdio_init_all();

  // Inicializa o I2C
  i2c_init(I2C_PORT, 400 * 1000); // Configura I2C para 400 kHz
  gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
  gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
  gpio_pull_up(SDA_PIN);
  gpio_pull_up(SCL_PIN);
  
  // Inicializa o display OLED
  ssd1306_init(I2C_PORT);
  ssd1306_clear();

  if (cyw43_arch_init()) {
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("Erro ao iniciar Wi-Fi"), get_center_y() - 5, "Erro ao iniciar Wi-Fi", true);
    ssd1306_update(I2C_PORT);
    return -1;
  }

  cyw43_arch_enable_sta_mode();

  const char *ssid = "SEU_WIFI"; // SEU_WIFI
  const char *password = "SUA_SENHA"; // SUA_SENHA

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

  while (true) {
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("Hello, world!"), get_center_y() - 5, "Hello, world!", true);
    ssd1306_update(I2C_PORT);
  }
}