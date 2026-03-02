# config.py — Configurações do BitDogLab
# Edite este arquivo com suas credenciais antes de fazer o upload para a placa.

# ── WiFi ──────────────────────────────────────────
WIFI_SSID     = "NomeDoSeuWiFi"
WIFI_PASSWORD = "SuaSenhaWiFi"

# ── Servidor ──────────────────────────────────────
# URL do endpoint de descoberta de serviços (Nó de Nomes).
# O firmware consultará este endpoint para descobrir o endereço WebSocket
# do servidor dinamicamente, sem URL hardcoded (transparência de localização).
DISCOVER_URL  = "http://192.168.1.100:8000/api/discover"

# Timeout de conexão WiFi (segundos)
WIFI_TIMEOUT  = 15

# ── Hardware GPIO (BitDogLab v6.3) ───────────────
JOY_X_PIN   = 26   # ADC — joystick eixo X
JOY_Y_PIN   = 27   # ADC — joystick eixo Y
JOY_BTN_PIN = 22   # Digital — botão do joystick

OLED_SDA    = 14   # I2C SDA
OLED_SCL    = 15   # I2C SCL
OLED_ADDR   = 0x3C # Endereço I2C do SSD1306

LED_MATRIX_PIN = 7  # WS2812B data pin
BUZZER_PIN     = 10

# ── Joystick thresholds ───────────────────────────
JOY_THRESHOLD = 10000  # ADC center ~32768; deslocamento mínimo para detectar direção
DEBOUNCE_MS   = 200
