"""
Driver do Joystick Analógico — BitDogLab v6.3
GPIO 26 = VRx (eixo X), GPIO 27 = VRy (eixo Y), GPIO 22 = Botão
O ADC do RP2040 retorna valores de 0–65535. Centro ≈ 32768.
"""

from machine import ADC, Pin
import utime
from config import JOY_X_PIN, JOY_Y_PIN, JOY_BTN_PIN, JOY_THRESHOLD, DEBOUNCE_MS


class Joystick:
    def __init__(self):
        self.adc_x   = ADC(Pin(JOY_X_PIN))
        self.adc_y   = ADC(Pin(JOY_Y_PIN))
        self.btn     = Pin(JOY_BTN_PIN, Pin.IN, Pin.PULL_UP)
        self._last_move_ms = 0

    def read_raw(self) -> tuple[int, int]:
        """Retorna (x, y) raw do ADC (0–65535)."""
        return self.adc_x.read_u16(), self.adc_y.read_u16()

    def read_direction(self) -> str | None:
        """
        Detecta a direção do joystick com debounce.
        Retorna "UP" | "DOWN" | "LEFT" | "RIGHT" | None
        """
        now = utime.ticks_ms()
        if utime.ticks_diff(now, self._last_move_ms) < DEBOUNCE_MS:
            return None

        x, y = self.read_raw()
        center = 32768
        th     = JOY_THRESHOLD

        direction = None
        if   y < center - th:  direction = "UP"
        elif y > center + th:  direction = "DOWN"
        elif x < center - th:  direction = "LEFT"
        elif x > center + th:  direction = "RIGHT"

        if direction:
            self._last_move_ms = now

        return direction

    def wait_for_move(self, timeout_ms: int = 8000) -> str | None:
        """
        Bloqueia até detectar um movimento no joystick ou timeout.
        Retorna a direção detectada ou None em caso de timeout.
        """
        start = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start) < timeout_ms:
            direction = self.read_direction()
            if direction:
                return direction
            utime.sleep_ms(20)
        return None
