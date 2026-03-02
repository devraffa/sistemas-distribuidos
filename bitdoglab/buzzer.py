"""
Buzzer — Feedback Sonoro BitDogLab
"""
from machine import Pin, PWM
import utime
from config import BUZZER_PIN


class Buzzer:
    def __init__(self):
        self.pwm = PWM(Pin(BUZZER_PIN))
        self.pwm.duty_u16(0)

    def _beep(self, freq: int, duration_ms: int):
        self.pwm.freq(freq)
        self.pwm.duty_u16(32768)
        utime.sleep_ms(duration_ms)
        self.pwm.duty_u16(0)

    def correct(self):
        """Tom alto curto — acerto."""
        self._beep(1000, 80)

    def wrong(self):
        """Tom baixo longo — erro."""
        self._beep(300, 400)

    def game_start(self):
        for f in [500, 700, 900]:
            self._beep(f, 100)
            utime.sleep_ms(40)

    def winner(self):
        for f in [600, 800, 1000, 1200]:
            self._beep(f, 120)
            utime.sleep_ms(30)

    def tick(self):
        """Clique leve para cada seta na sequência."""
        self._beep(700, 50)
