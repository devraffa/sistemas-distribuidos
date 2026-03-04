# Pico Pi Memory — Jogo da Memória Distribuído

> **Projeto de Sistemas Distribuídos** — Comunicação WebSocket/RPC, Relógios de Lamport, Circuit Breaker, Retry e Nó de Nomes.

Jogo da memória multiplayer onde jogadores usam placas **BitDogLab** (Raspberry Pi Pico W) ou browser para competir. O servidor exibe sequências crescentes de setas (↑↓←→) e os jogadores devem replicá-las. Quem errar é eliminado; o último sobrevivente vence.

---

## 📐 Arquitetura

```
BitDogLab (Pico W)  ←── WebSocket ──►  Servidor FastAPI  ◄── WebSocket ──►  Browser
   MicroPython                           asyncio + SQLite                    HTML/JS
   OLED + Joystick
```

## ✅ Requisitos de SD Implementados

| Requisito | Implementação | Arquivo |
|---|---|---|
| **Comunicação RPC** | WebSocket — cliente nunca toca sockets diretamente | `ws_client.js`, `bitdoglab/ws_client.py` |
| **N-Camadas** | Apresentação / Lógica / Persistência | `frontend/`, `server/`, `server/db/` |
| **Concorrência** | FastAPI asyncio — múltiplos clientes simultâneos | `server/main.py` |
| **Retry** | Reconexão com backoff exponencial (1s→2s→4s) | `server/middleware/retry.py` |
| **Circuit Breaker** | Protege a camada SQLite (CLOSED→OPEN→HALF-OPEN) | `server/middleware/circuit_breaker.py` |
| **Relógio de Lamport** | Ordena eventos de jogo entre todos os nós | `server/middleware/lamport_clock.py` |
| **Nó de Nomes** | `/api/discover` — BitDogLab descobre servidor dinamicamente | `server/middleware/name_node.py` |

---

## 🚀 Como Executar

### 1. Instalar dependências do servidor

```bash
cd server
pip install -r requirements.txt
```

### 2. Iniciar o servidor

```bash
cd server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

O servidor estará em: `http://localhost:8000`

### 3. Abrir o frontend no browser

Acesse `http://localhost:8000` — o próprio servidor serve o frontend.

| Página | URL |
|---|---|
| Lobby | `http://localhost:8000/` |
| Partida | `http://localhost:8000/game` |
| Placar | `http://localhost:8000/scoreboard` |
| Status SD | `http://localhost:8000/api/status` |

### 4. Configurar o BitDogLab

1. Edite `bitdoglab/config.py` com:
   - `WIFI_SSID` e `WIFI_PASSWORD`
   - `DISCOVER_URL` com o IP da máquina que roda o servidor (ex: `http://192.168.1.100:8000/api/discover`)

2. Copie toda a pasta `bitdoglab/` para a placa Pico W usando **Thonny** (File → Save to Device):
   ```
   main.py, config.py, ws_client.py, oled_display.py,
   joystick.py, led_matrix.py, buzzer.py
   ```

3. Reinicie a placa — ela conecta ao WiFi, descobre o servidor e aparece no lobby.

---

## 📁 Estrutura do Projeto

```
sistemas-distribuidos/
├── server/
│   ├── main.py                    ← Entry point FastAPI
│   ├── requirements.txt
│   ├── game/
│   │   ├── engine.py              ← Lógica do jogo + Lamport
│   │   ├── room_manager.py        ← Salas
│   │   └── models.py              ← Dataclasses
│   ├── middleware/
│   │   ├── circuit_breaker.py     ← Circuit Breaker (DB)
│   │   ├── retry.py               ← Retry + backoff
│   │   ├── lamport_clock.py       ← Relógio de Lamport
│   │   └── name_node.py           ← Nó de Nomes
│   └── db/
│       └── database.py            ← SQLite (aiosqlite)
│
├── frontend/
│   ├── index.html                 ← Lobby
│   ├── game.html                  ← Partida ao vivo
│   ├── scoreboard.html            ← Placar global
│   ├── css/style.css
│   └── js/ws_client.js            ← Abstração WebSocket
│
└── bitdoglab/
    ├── main.py                    ← Firmware principal
    ├── config.py                  ← Configurações (editar)
    ├── ws_client.py               ← Client WS MicroPython
    ├── oled_display.py            ← Driver OLED SSD1306
    ├── joystick.py                ← Driver Joystick ADC
    ├── led_matrix.py              ← WS2812B 5x5
    └── buzzer.py                  ← Feedback sonoro PWM
```

---

## 🎲 Fluxo de Jogo

1. **Lobby**: Host cria sala no browser → código de 6 letras gerado
2. **Entrada**: Demais jogadores entram com o código (browser ou BitDogLab)
3. **Host inicia**: Partida começa quando há ≥2 jogadores
4. **Rodadas** (sequência cresce +1 por rodada):
   - Servidor exibe sequência de setas (OLED + browser)
   - Cada jogador responde em turnos com o joystick ou botões do browser
   - Timer de 8s por jogador
   - Quem errar ou demorar → eliminado
5. **Fim**: Último sobrevivente vence; scoreboard salvo no SQLite

---

## 🔌 Protocolo WebSocket

| Direção | Tipo | Descrição |
|---|---|---|
| C→S | `identify` | Nome + tipo de dispositivo |
| C→S | `create_room` | Host cria sala |
| C→S | `join_room` | Entrar em sala com código |
| C→S | `start_game` | Host inicia partida |
| C→S | `player_move` | Movimento do joystick `{direction, lamport_ts}` |
| S→C | `show_arrow` | Seta a exibir `{arrow, position, total}` |
| S→C | `your_turn` | Vez do jogador `{timeout_ms}` |
| S→C | `move_result` | Resultado `{correct}` |
| S→C | `player_eliminated` | Jogador eliminado |
| S→C | `game_over` | Fim de jogo `{winner, scoreboard}` |

Todas as mensagens carregam `lamport_ts` para ordenação causal.
