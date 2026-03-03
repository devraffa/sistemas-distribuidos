#include "pico/cyw43_arch.h"

// utils
#include "utils/utils.h"

int connect_wifi() {
  const char *ssid = "brisa-4208840";     // SEU_WIFI
  const char *password = "wydqhiiw";      // SUA_SENHA

  if (cyw43_arch_init()) {
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("Erro ao iniciar Wi-Fi"),
                        get_center_y() - 5, "Erro ao iniciar Wi-Fi", true);
    ssd1306_update(I2C_PORT);
    return 0;
  }

  cyw43_arch_enable_sta_mode();

  while (true) {
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("Conectando Wi-Fi..."), get_center_y() - 5,
                        "Conectando Wi-Fi...", true);
    ssd1306_draw_string(get_center_x(ssid), get_center_y() + 5, ssid, true);
    ssd1306_update(I2C_PORT);

    if (cyw43_arch_wifi_connect_timeout_ms(ssid, password,
                                           CYW43_AUTH_WPA2_AES_PSK, 30000)) {
      ssd1306_clear();
      ssd1306_draw_string(get_center_x("Falha ao conectar"), get_center_y() - 5,
                          "Falha ao conectar", true);
      ssd1306_update(I2C_PORT);
      sleep_ms(2000); // aguarda 2 segundos antes de tentar de novo
    } else {
      ssd1306_clear();
      ssd1306_draw_string(get_center_x("Conectado!"), get_center_y() - 5,
                          "Conectado!", true);
      ssd1306_update(I2C_PORT);
      break; // Sai do loop quando conectar com sucesso
    }
  }
  sleep_ms(5000);
  return 1;
}

int main() {
  // Variáveis para armazenar os valores do joystick
  char str_x[50];
  char str_y[50];

  // IP do computador na rede local para o MQTT
  const char *pc_ip = "192.168.1.11";

  // Inicia o sistema
  stdio_init_all();
  init_tela();
  init_joystick();

  // Conecta na rede Wi-Fi
  if (!connect_wifi())
    return -1;

  // Inicializa o protocolo MQTT
  init_mqtt(pc_ip);

  // Pequeno delay para garantir a conexão antes de enviar
  sleep_ms(2000);
  mqtt_pub_start();

  while (true) {
    print_joystick(str_x, str_y, sizeof(str_x), 11);
  }
}