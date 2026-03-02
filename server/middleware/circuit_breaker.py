"""
Circuit Breaker — Protege a camada de persistência (SQLite)
------------------------------------------------------------
Padrão Circuit Breaker com 3 estados:

  CLOSED   → Operação normal. Falhas são contadas.
  OPEN     → Limiar de falhas atingido. Chamadas bloqueadas por `reset_timeout` segundos.
  HALF-OPEN → Timeout expirou. Permite UMA chamada de teste para ver se o serviço voltou.

Ao proteger o banco de dados com este padrão, mesmo que o SQLite fique
indisponível, o servidor continua aceitando conexões e o jogo prossegue
(sem persistência temporariamente), evitando falha em cascata.
"""

import asyncio
import time
from enum import Enum
from functools import wraps


class CBState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Levantada quando o circuito está aberto e a chamada é bloqueada."""
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_timeout: float = 10.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

        self._state = CBState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CBState:
        if self._state == CBState.OPEN:
            # Verifica se o timeout de reset já passou → tenta HALF_OPEN
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                self._state = CBState.HALF_OPEN
        return self._state

    def _on_success(self):
        self._failure_count = 0
        self._state = CBState.CLOSED

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CBState.OPEN
            print(
                f"[CircuitBreaker:{self.name}] OPEN apos {self._failure_count} falhas"
            )

    async def call(self, coro):
        """
        Executa `coro` (coroutine) protegido pelo Circuit Breaker.
        Levanta CircuitBreakerOpenError se o circuito estiver aberto.
        """
        current_state = self.state  # atualiza estado (OPEN→HALF_OPEN se timeout passou)

        if current_state == CBState.OPEN:
            raise CircuitBreakerOpenError(
                f"[CircuitBreaker:{self.name}] Circuito ABERTO — chamada bloqueada"
            )

        try:
            result = await coro
            self._on_success()
            if current_state == CBState.HALF_OPEN:
                print(f"[CircuitBreaker:{self.name}] CLOSED - servico recuperado")
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def __repr__(self):
        return f"CircuitBreaker(name={self.name}, state={self._state}, failures={self._failure_count})"


# Instância global protegendo o banco de dados
db_circuit_breaker = CircuitBreaker(name="sqlite_db", failure_threshold=3, reset_timeout=10.0)
