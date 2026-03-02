"""
Retry com Backoff Exponencial
------------------------------
Tenta reexecutar uma coroutine que falhou, aguardando intervalos
crescentes entre cada tentativa (1s, 2s, 4s por padrão).

Diferença do Circuit Breaker:
- Retry: executa a operação novamente até ter sucesso ou esgotar tentativas.
- Circuit Breaker: *para* de tentar quando detecta falha sistêmica prolongada.

Uso no projeto:
- Servidor: tentar reenviar mensagem WebSocket para cliente momentaneamente offline.
- BitDogLab: tentar reconectar ao servidor após queda de WiFi.
"""

import asyncio
from typing import Callable, Type


async def retry_with_backoff(
    coro_factory: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    on_retry=None,
):
    """
    Executa `coro_factory()` com retry e backoff exponencial.

    Args:
        coro_factory: Callable que retorna uma nova coroutine a cada chamada.
        max_attempts: Número máximo de tentativas.
        base_delay: Delay inicial em segundos (dobra a cada tentativa).
        exceptions: Tipos de exceção que disparam retry.
        on_retry: Callback opcional chamado com (attempt, delay, exc) antes de cada retry.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except exceptions as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s...
            if on_retry:
                on_retry(attempt, delay, exc)
            else:
                print(
                    f"[Retry] Tentativa {attempt}/{max_attempts} falhou: {exc}. "
                    f"Aguardando {delay}s..."
                )
            await asyncio.sleep(delay)
    raise last_exc
