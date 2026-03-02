"""
Relógio Lógico de Lamport
--------------------------
Cada evento no sistema carrega um timestamp lógico.
- Ao ENVIAR: incrementa o relógio local e anexa ao evento.
- Ao RECEBER: atualiza o relógio com max(local, recebido) + 1.

Isso garante que eventos causalmente relacionados sejam ordenados
corretamente mesmo sem sincronização de relógio físico entre os nós.
"""


class LamportClock:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._time = 0

    def tick(self) -> int:
        """Incrementa antes de enviar um evento. Retorna o novo timestamp."""
        self._time += 1
        return self._time

    def update(self, received_time: int) -> int:
        """
        Atualiza o relógio ao receber um evento com timestamp remoto.
        Aplica: local = max(local, received) + 1
        """
        self._time = max(self._time, received_time) + 1
        return self._time

    @property
    def time(self) -> int:
        return self._time

    def __repr__(self):
        return f"LamportClock(node={self.node_id}, t={self._time})"


# Relógio global do servidor
server_clock = LamportClock(node_id="server")
