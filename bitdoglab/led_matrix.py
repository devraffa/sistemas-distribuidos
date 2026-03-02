"""
Controle da Matriz LED 5x5 WS2812B — BitDogLab
"""

from machine import Pin
import neopixel
import utime
from config import LED_MATRIX_PIN

N_LEDS = 25  # 5x5


class LEDMatrix:
    def __init__(self):
        self.np = neopixel.NeoPixel(Pin(LED_MATRIX_PIN), N_LEDS)
        self.clear()

    def clear(self):
        for i in range(N_LEDS):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def fill(self, r: int, g: int, b: int):
        for i in range(N_LEDS):
            self.np[i] = (r, g, b)
        self.np.write()

    def flash(self, r: int, g: int, b: int, times: int = 2, delay_ms: int = 150):
        for _ in range(times):
            self.fill(r, g, b)
            utime.sleep_ms(delay_ms)
            self.clear()
            utime.sleep_ms(delay_ms)

    def show_correct(self):
        """Verde — resposta correta."""
        self.flash(0, 30, 0, times=2, delay_ms=120)

    def show_wrong(self):
        """Vermelho — resposta errada."""
        self.flash(30, 0, 0, times=3, delay_ms=120)

    def show_arrow(self, direction: str):
        """Ilumina LEDs formando uma seta na direção dada."""
        # Patterns 5x5 para cada direção (1=ligado, 0=apagado), row-major
        patterns = {
            "UP": [
                0,0,1,0,0,
                0,1,1,1,0,
                1,1,1,1,1,
                0,0,1,0,0,
                0,0,1,0,0,
            ],
            "DOWN": [
                0,0,1,0,0,
                0,0,1,0,0,
                1,1,1,1,1,
                0,1,1,1,0,
                0,0,1,0,0,
            ],
            "LEFT": [
                0,0,1,0,0,
                0,1,0,0,0,
                1,1,1,1,1,
                0,1,0,0,0,
                0,0,1,0,0,
            ],
            "RIGHT": [
                0,0,1,0,0,
                0,0,0,1,0,
                1,1,1,1,1,
                0,0,0,1,0,
                0,0,1,0,0,
            ],
        }
        pat = patterns.get(direction, [0] * 25)
        colors = {"UP": (0, 30, 0), "DOWN": (30, 0, 0), "LEFT": (0, 0, 30), "RIGHT": (30, 20, 0)}
        color = colors.get(direction, (20, 20, 20))
        for i, on in enumerate(pat):
            self.np[i] = color if on else (0, 0, 0)
        self.np.write()

    def show_winner(self):
        """Animação arco-íris para vencedor."""
        colors = [(30,0,0),(30,15,0),(30,30,0),(0,30,0),(0,0,30)]
        for _ in range(3):
            for c in colors:
                self.fill(*c)
                utime.sleep_ms(100)
        self.clear()
