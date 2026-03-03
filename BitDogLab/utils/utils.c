#include "utils.h"
#include "lwip/apps/mqtt.h"
#include "lwip/dns.h"

static mqtt_client_t *static_mqtt_client;
static ip_addr_t mqtt_broker_address;

// Callback chamado quando a conexão com o broker termina (sucesso ou falha)
static void mqtt_connection_cb(mqtt_client_t *client, void *arg,
                               mqtt_connection_status_t status) {
  if (status == MQTT_CONNECT_ACCEPTED) {
    printf("MQTT: Conectado ao broker com sucesso!\n");
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("sucesso!"), get_center_y(), "sucesso!", true);
    ssd1306_update(I2C_PORT);
  } else {
    printf("MQTT: Falha na conexão, status: %d\n", status);
    ssd1306_clear();
    ssd1306_draw_string(get_center_x("falha!"), get_center_y(), "falha!", true);
    ssd1306_update(I2C_PORT);
  }
}

// Função para publicar uma mensagem
void mqtt_pub_start(void) {
  const char *pub_payload = "start";
  err_t err = mqtt_publish(static_mqtt_client, "play/sd", pub_payload,
                           strlen(pub_payload), 0, 0, NULL, NULL);

  if (err != ERR_OK) {
    printf("Erro ao publicar: %d\n", err);
  } else {
    printf("Mensagem enviada!\n");
  }
}

void init_mqtt(const char *ip_address) {
  printf("Iniciando MQTT\n");

  static_mqtt_client = mqtt_client_new();

  // Substitua pelo IP do seu PC onde o Mosquitto está rodando
  ip4addr_aton(ip_address, &mqtt_broker_address);

  struct mqtt_connect_client_info_t ci;
  memset(&ci, 0, sizeof(ci));
  ci.client_id = "PicoW_Cl";
  ci.keep_alive = 60;

  // Tenta conectar
  printf("Conectando ao broker MQTT...\n");

  ssd1306_clear();
  ssd1306_draw_string(get_center_x("Conect. broker..."), get_center_y(), "Conect. broker...", true);
  ssd1306_update(I2C_PORT);

  sleep_ms(2000);

  mqtt_client_connect(static_mqtt_client, &mqtt_broker_address, MQTT_PORT,
                      mqtt_connection_cb, NULL, &ci);
}

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

void print_joystick(char *str_x, char *str_y, size_t buffer_size,
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
  ssd1306_draw_string(get_center_x(str_x), get_center_y() - 5, str_x, true);
  ssd1306_draw_string(get_center_x(str_y), get_center_y() + 5, str_y, true);
  ssd1306_update(I2C_PORT);
}