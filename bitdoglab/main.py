"""
main.py — Firmware BitDogLab (Raspberry Pi Pico W)
====================================================
Fluxo:
  1. Conecta ao WiFi
  2. Descobre o servidor via Nó de Nomes (/api/discover)
  3. Conecta via WebSocket (com Retry + backoff)
  4. Identifica-se com nome e device_type="bitdoglab"
  5. Loop do jogo: exibe setas no OLED + LEDs, lê joystick, envia respostas
  6. Feedback visual (LEDs) e sonoro (buzzer) em tempo real
"""

import network
import urequests
import ujson
import utime
import os

from config    import (WIFI_SSID, WIFI_PASSWORD, WIFI_TIMEOUT,
                       DISCOVER_URL)
from ws_client  import WSClient
from oled_display import OLEDDisplay
from joystick   import Joystick
from led_matrix import LEDMatrix
from buzzer     import Buzzer

# ── Generate unique player ID ──────────────────────────────────
def gen_player_id() -> str:
    raw = os.urandom(6)
    return ''.join(f'{b:02x}' for b in raw)

PLAYER_ID   = gen_player_id()
PLAYER_NAME = "BitDog-" + PLAYER_ID[:4]


# ── WiFi connection ────────────────────────────────────────────
def connect_wifi(oled: OLEDDisplay) -> bool:
    oled.show_text(["Conectando", "ao WiFi...", WIFI_SSID[:12]], y_start=12)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    start = utime.ticks_ms()
    while not wlan.isconnected():
        if utime.ticks_diff(utime.ticks_ms(), start) > WIFI_TIMEOUT * 1000:
            oled.show_text(["WiFi falhou!", "Verifique", "config.py"], y_start=12)
            return False
        utime.sleep_ms(300)

    ip = wlan.ifconfig()[0]
    oled.show_text(["WiFi OK!", ip], y_start=20)
    utime.sleep_ms(1000)
    return True


# ── Service discovery (Name Node) ──────────────────────────────
def discover_server(oled: OLEDDisplay) -> tuple[str, int, str] | None:
    """
    Consulta o Nó de Nomes para descobrir o servidor dinamicamente.
    Retorna (host, port, path) ou None se falhar.
    """
    oled.show_text(["Descobrindo", "servidor...", "Name Node"], y_start=12)
    for attempt in range(3):
        try:
            r = urequests.get(DISCOVER_URL, timeout=5)
            data = ujson.loads(r.text)
            r.close()
            services = data.get("services", [])
            if services:
                ws_url = services[0]["ws_url"]
                # ws://192.168.1.100:8000/ws/{player_id}
                ws_url = ws_url.replace("{player_id}", PLAYER_ID)
                # Parse host, port, path
                parts = ws_url.replace("ws://", "").split("/", 1)
                host_port = parts[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 80
                path = "/" + (parts[1] if len(parts) > 1 else "")
                oled.show_text(["Servidor OK!", host[:14]], y_start=24)
                utime.sleep_ms(800)
                return host, port, path
        except Exception as e:
            delay = 1000 * (2 ** attempt)
            oled.show_text([f"Retry {attempt+1}/3", str(e)[:14]], y_start=20)
            utime.sleep_ms(delay)

    oled.show_text(["Srv nao", "encontrado!", "Verifique IP"], y_start=12)
    return None


# ── Main game loop ─────────────────────────────────────────────
def run():
    oled  = OLEDDisplay()
    joy   = Joystick()
    leds  = LEDMatrix()
    buzz  = Buzzer()
    ws    = WSClient()

    oled.show_text(["MemoryArrows", "BitDogLab", PLAYER_ID[:8]], y_start=10)
    utime.sleep_ms(1500)

    # 1. WiFi
    if not connect_wifi(oled):
        return

    # 2. Descoberta (Name Node)
    srv = discover_server(oled)
    if not srv:
        return
    host, port, path = srv

    # 3. Conectar WebSocket (com Retry)
    oled.show_text(["Conectando", "WebSocket...", f"{host}:{port}"], y_start=10)
    try:
        ws.connect(host, port, path, max_attempts=3)
    except Exception as e:
        oled.show_text(["WS falhou!", str(e)[:14]], y_start=22)
        return

    # 4. Identificação
    ws.send({"type": "identify", "name": PLAYER_NAME, "device_type": "bitdoglab"})
    msg = ws.receive()
    if not msg or msg.get("type") != "identified":
        oled.show_text(["Ident. falhou"], y_start=28)
        return

    # 5. Aguarda sala (host cria via browser, BitDog entra informando room_id)
    # Por simplicidade: a placa aguarda um QR ou mostra instrução para digitar no browser
    oled.show_text(["Conectado!", PLAYER_NAME, "Aguardando", "sala..."], y_start=4)
    ws.send({"type": "ping"})

    eliminated = False
    winner     = False
    my_room    = None

    while True:
        msg = ws.receive()
        if msg is None:
            utime.sleep_ms(50)
            continue

        t = msg.get("type")

        if t == "room_created" or t == "player_joined":
            room = msg.get("room", {})
            my_room = room.get("id", "?")
            oled.show_lobby(PLAYER_NAME, my_room)

        elif t == "game_started":
            oled.show_text(["JOGO INICIO!", "Memorize as", "setas!"], y_start=14)
            buzz.game_start()
            leds.clear()

        elif t == "round_start":
            rnd = msg.get("round", "?")
            oled.show_sequence_start(rnd)
            utime.sleep_ms(500)

        elif t == "show_sequence_start":
            length = msg.get("length", 0)
            oled.show_sequence_start(length)

        elif t == "show_arrow":
            direction = msg.get("arrow", "UP")
            oled.show_arrow(direction)
            leds.show_arrow(direction)
            buzz.tick()
            utime.sleep_ms(200)

        elif t == "show_sequence_end":
            oled.show_text(["Memorize!", "Pronto?"], y_start=20)
            leds.clear()

        elif t == "your_turn":
            timeout_ms = msg.get("timeout_ms", 8000)
            seq_len    = msg.get("sequence_length", 1)
            oled.show_your_turn(0, seq_len)
            leds.clear()

            # Lê joystick para cada seta da sequência
            for move_i in range(seq_len):
                oled.show_your_turn(move_i, seq_len)
                direction = joy.wait_for_move(timeout_ms=timeout_ms)
                if direction is None:
                    # Timeout
                    ws.send({"type": "player_move", "direction": "NONE"})
                    break
                leds.show_arrow(direction)
                ws.send({"type": "player_move", "direction": direction})

                # Aguarda resultado
                result = ws.receive()
                if result and result.get("type") == "move_result":
                    correct = result.get("correct", False)
                    if correct:
                        oled.show_move_result(True)
                        leds.show_correct()
                        buzz.correct()
                    else:
                        oled.show_move_result(False)
                        leds.show_wrong()
                        buzz.wrong()
                        break
                utime.sleep_ms(100)

        elif t == "waiting_for_player":
            name = msg.get("player_name", "outro")
            oled.show_waiting(name)
            leds.clear()

        elif t == "player_eliminated":
            player = msg.get("player", {})
            if player.get("id") == PLAYER_ID:
                eliminated = True
                oled.show_eliminated()
                leds.show_wrong()
                buzz.wrong()
                utime.sleep_ms(2000)
                oled.show_text(["Voce foi", "eliminado!", "Assistindo..."], y_start=12)

        elif t == "game_over":
            w = msg.get("winner")
            if w and w.get("name") == PLAYER_NAME:
                winner = True
                oled.show_winner()
                leds.show_winner()
                buzz.winner()
            else:
                winner_name = w.get("name", "?") if w else "Nenhum"
                oled.show_text(["Fim de Jogo!", "Vencedor:", winner_name[:12]], y_start=10)
                leds.clear()
            utime.sleep_ms(5000)
            oled.show_lobby(PLAYER_NAME, my_room or "")
            break


# ── Entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"[FATAL] {e}")
        from oled_display import OLEDDisplay
        try:
            OLEDDisplay().show_text(["ERRO FATAL", str(e)[:14]], y_start=20)
        except:
            pass
