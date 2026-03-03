#include "pico/cyw43_arch.h"

// utils
#include "utils/utils.h"

// comunicação com o server
#include "lwip/pbuf.h"
#include "lwip/tcp.h"
#include "lwip/dns.h"
#include "lwip/init.h"
#include "lwip/ip_addr.h"

#define SERVER_IP "192.168.1.11" // Substitua pelo IP que você pegou no terminal
#define SERVER_PORT 8000

// Variáveis globais para armazenar os valores brutos lidos
uint current_joy_x = 0;
uint current_joy_y = 0;

// Callback executado quando o servidor responde e a conexão pode ser fechada
static err_t http_recv_cb(void *arg, struct tcp_pcb *tpcb, struct pbuf *p, err_t err) {
    if (p == NULL) {
        tcp_close(tpcb);
        return ERR_OK;
    }
    tcp_recved(tpcb, p->tot_len); // Confirma o recebimento dos bytes
    pbuf_free(p);
    return ERR_OK;
}

// Callback para erros de conexão
static void http_err_cb(void *arg, err_t err) {
    printf("Erro na conexão TCP: %d\n", err);
}

// Callback executado assim que a conexão TCP é estabelecida
static err_t http_connected_cb(void *arg, struct tcp_pcb *tpcb, err_t err) {
    if (err != ERR_OK) {
        printf("Falha ao conectar no servidor FastAPI\n");
        return err;
    }

    // 1. Monta o payload JSON idêntico ao que o Pydantic espera
    char payload[100];
    snprintf(payload, sizeof(payload), "{\"player_id\":\"p1\",\"x_pos\":%d,\"y_pos\":%d}", current_joy_x, current_joy_y);

    // 2. Monta o cabeçalho HTTP POST completo
    char request[512];
    snprintf(request, sizeof(request),
             "POST /rpc/update_position HTTP/1.1\r\n"
             "Host: %s\r\n"
             "Content-Type: application/json\r\n"
             "Content-Length: %d\r\n"
             "Connection: close\r\n"
             "\r\n"
             "%s", SERVER_IP, strlen(payload), payload);

    // 3. Escreve e dispara os dados na rede
    tcp_write(tpcb, request, strlen(request), TCP_WRITE_FLAG_COPY);
    tcp_output(tpcb);

    // 4. Define o callback de recebimento para fechar a porta adequadamente
    tcp_recv(tpcb, http_recv_cb);
    return ERR_OK;
}

// Função de disparo que chamaremos no loop principal
void send_joystick_state() {
    ip_addr_t server_ip;
    ipaddr_aton(SERVER_IP, &server_ip);

    // O uso de cyw43_arch_lwip_begin() e end() é obrigatório para manter thread-safety
    cyw43_arch_lwip_begin();
    struct tcp_pcb *pcb = tcp_new();
    if (pcb) {
        tcp_err(pcb, http_err_cb);
        tcp_connect(pcb, &server_ip, SERVER_PORT, http_connected_cb);
    }
    cyw43_arch_lwip_end();
}

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

  // Inicia o sistema
  stdio_init_all();
  init_tela();
  init_joystick();

  // Conecta na rede Wi-Fi
  if (!connect_wifi())
    return -1;

  while (true) {
    print_joystick(str_x, str_y, sizeof(str_x), 11);

    // Lê os valores brutos do joystick 
    adc_select_input(0);
    current_joy_y = adc_read();
    adc_select_input(1);
    current_joy_x = adc_read();

    // Dispara a requisição HTTP POST para o FastAPI
    send_joystick_state();

    // Taxa de atualização: 100ms (10 requisições por segundo)
    sleep_ms(100); 
  }
}