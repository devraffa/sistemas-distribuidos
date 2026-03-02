"""
Driver OLED SSD1306 — BitDogLab
Exibe setas grandes (↑↓←→), mensagens de lobby, eliminação e vitória.
Usa a biblioteca ssd1306 embutida no firmware do BitDogLab.
"""

from machine import I2C, Pin
import ssd1306
from config import OLED_SDA, OLED_SCL, OLED_ADDR

WIDTH  = 128
HEIGHT = 64

# Setas grandes desenhadas pixel a pixel (mapa de linhas)
ARROW_SPRITES = {
    "UP": [
        "    ****    ",
        "   ******   ",
        "  ********  ",
        " ****  **** ",
        "    ****    ",
        "    ****    ",
        "    ****    ",
        "    ****    ",
    ],
    "DOWN": [
        "    ****    ",
        "    ****    ",
        "    ****    ",
        "    ****    ",
        " ****  **** ",
        "  ********  ",
        "   ******   ",
        "    ****    ",
    ],
    "LEFT": [
        "    *       ",
        "   **       ",
        "  ** *******",
        " ** ********",
        " ** ********",
        "  ** *******",
        "   **       ",
        "    *       ",
    ],
    "RIGHT": [
        "       *    ",
        "       **   ",
        "*******  ** ",
        "********  **",
        "********  **",
        "*******  ** ",
        "       **   ",
        "       *    ",
    ],
}


class OLEDDisplay:
    def __init__(self):
        i2c = I2C(1, sda=Pin(OLED_SDA), scl=Pin(OLED_SCL), freq=400_000)
        self.oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=OLED_ADDR)
        self.clear()

    def clear(self):
        self.oled.fill(0)
        self.oled.show()

    def show_text(self, lines: list[str], y_start: int = 0, center: bool = True):
        """Exibe até 4 linhas de texto (8px por linha)."""
        self.oled.fill(0)
        for i, line in enumerate(lines[:8]):
            x = max(0, (WIDTH - len(line) * 8) // 2) if center else 2
            self.oled.text(line, x, y_start + i * 10)
        self.oled.show()

    def show_arrow(self, direction: str):
        """Exibe uma seta grande centralizada no OLED."""
        self.oled.fill(0)
        sprite = ARROW_SPRITES.get(direction, [])
        scale  = 4  # cada '*' vira 4x4 pixels
        x_off  = (WIDTH  - 12 * scale) // 2
        y_off  = (HEIGHT - len(sprite) * scale) // 2
        for row_i, row in enumerate(sprite):
            for col_i, ch in enumerate(row):
                if ch == '*':
                    for dy in range(scale):
                        for dx in range(scale):
                            self.oled.pixel(
                                x_off + col_i * scale + dx,
                                y_off + row_i * scale + dy,
                                1
                            )
        self.oled.show()

    def show_lobby(self, player_name: str, room_code: str = ""):
        lines = [
            "MemoryArrows",
            "------------",
            player_name[:12],
        ]
        if room_code:
            lines += ["Sala: " + room_code, "Aguardando..."]
        else:
            lines += ["Conectando..."]
        self.show_text(lines, y_start=4)

    def show_sequence_start(self, length: int):
        self.show_text([
            "  MEMORIZE!  ",
            f" {length} seta(s) ",
            "  Prepare-se ",
        ], y_start=14)

    def show_your_turn(self, move_index: int, total: int):
        self.show_text([
            "  SUA VEZ!  ",
            f"  {move_index}/{total}  ",
            " Mova o joy ",
        ], y_start=14)

    def show_move_result(self, correct: bool):
        if correct:
            self.show_text(["  CORRETO!  ", "    :)    "], y_start=20)
        else:
            self.show_text(["   ERROU!   ", "    :(    "], y_start=20)

    def show_eliminated(self):
        self.show_text([
            " ELIMINADO  ",
            "   x_x     ",
            " Boa sorte! ",
        ], y_start=14)

    def show_winner(self):
        self.show_text([
            " VOCE VENCEU",
            "   \\o/      ",
            " Parabens!  ",
        ], y_start=14)

    def show_waiting(self, player_name: str):
        self.show_text([
            "Aguardando",
            player_name[:12],
            "...",
        ], y_start=16)

    def show_countdown(self, n: int):
        self.show_text([str(n)], y_start=24)
