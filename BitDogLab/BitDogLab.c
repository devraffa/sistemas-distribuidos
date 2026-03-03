// utils
#include "utils/utils.h"

int main() {
  // Variáveis para armazenar os valores do joystick
  char str_x[50];
  char str_y[50];

  // Inicia o sistema
  stdio_init_all();
  init_tela();
  init_joystick();

  // Conecta na rede Wi-Fi
  if (!connect_wifi()) return -1;

  while (true) {
    print_joystick(str_x, str_y, sizeof(str_x), 11);
  }
}