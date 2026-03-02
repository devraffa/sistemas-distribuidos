"""
Nó de Nomes (Service Registry / Name Node)
-------------------------------------------
Implementa um registro centralizado de serviços no estilo DNS simplificado.

Permite que o BitDogLab (e qualquer cliente) descubra o endereço do servidor
de jogo dinamicamente, sem URL hardcoded no firmware. O cliente consulta o
endpoint /api/discover e recebe o endereço WebSocket do servidor ativo.

Isso implementa o requisito de Descoberta de Serviços (transparência de localização).
"""

import time
from typing import Optional


class ServiceRecord:
    def __init__(self, name: str, ws_url: str, http_url: str, description: str = ""):
        self.name = name
        self.ws_url = ws_url
        self.http_url = http_url
        self.description = description
        self.registered_at = time.time()
        self.last_heartbeat = time.time()
        self.healthy = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ws_url": self.ws_url,
            "http_url": self.http_url,
            "description": self.description,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "healthy": self.healthy,
        }


class NameNode:
    """
    Registro de serviços. Armazena servidores de jogo disponíveis.
    Com TTL: serviços sem heartbeat por mais de `ttl` segundos são marcados como unhealthy.
    """

    def __init__(self, ttl: float = 30.0):
        self._registry: dict[str, ServiceRecord] = {}
        self.ttl = ttl

    def register(self, name: str, ws_url: str, http_url: str, description: str = "") -> ServiceRecord:
        record = ServiceRecord(name=name, ws_url=ws_url, http_url=http_url, description=description)
        self._registry[name] = record
        print(f"[NameNode] Servico registrado: {name} -> {ws_url}")
        return record

    def heartbeat(self, name: str) -> bool:
        if name in self._registry:
            self._registry[name].last_heartbeat = time.time()
            self._registry[name].healthy = True
            return True
        return False

    def lookup(self, name: str) -> Optional[ServiceRecord]:
        record = self._registry.get(name)
        if record:
            self._check_ttl(record)
        return record

    def list_healthy(self) -> list[dict]:
        now = time.time()
        result = []
        for record in self._registry.values():
            self._check_ttl(record)
            if record.healthy:
                result.append(record.to_dict())
        return result

    def _check_ttl(self, record: ServiceRecord):
        if time.time() - record.last_heartbeat > self.ttl:
            record.healthy = False


# Instância global do Nó de Nomes
name_node = NameNode(ttl=30.0)
