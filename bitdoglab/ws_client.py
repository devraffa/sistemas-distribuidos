"""
Cliente WebSocket MicroPython — BitDogLab
------------------------------------------
Abstrai completamente o socket da lógica do firmware.
O main.py nunca interage com sockets diretamente.

Protocolo:
  - Conecta via TCP + handshake WebSocket manualmente
  - Envia/recebe frames WebSocket (text frames, sem fragmentação)
  - Injeta timestamp de Lamport em cada mensagem enviada
  - Implementa Retry com backoff exponencial na reconexão
"""

import usocket
import ussl
import ujson
import ubinascii
import os
import utime


def _ws_handshake_key():
    raw = os.urandom(16)
    return ubinascii.b2a_base64(raw).decode().strip()


class WSClient:
    def __init__(self):
        self._sock    = None
        self._lamport = 0
        self._server_host = None
        self._server_port = None
        self._path        = None

    # ── Lamport ────────────────────────────────────────────────
    def _tick(self) -> int:
        self._lamport += 1
        return self._lamport

    def _update(self, received: int):
        self._lamport = max(self._lamport, received) + 1

    @property
    def lamport(self):
        return self._lamport

    # ── Connect ────────────────────────────────────────────────
    def connect(self, host: str, port: int, path: str, max_attempts: int = 3):
        """Conecta ao servidor WebSocket com Retry + backoff exponencial."""
        self._server_host = host
        self._server_port = port
        self._path        = path

        for attempt in range(1, max_attempts + 1):
            try:
                self._do_connect(host, port, path)
                print(f"[WSClient] Conectado em ws://{host}:{port}{path}")
                return
            except Exception as e:
                delay = 1000 * (2 ** (attempt - 1))  # 1s, 2s, 4s
                print(f"[WSClient] Tentativa {attempt}/{max_attempts} falhou: {e}. Aguardando {delay}ms...")
                utime.sleep_ms(delay)
        raise RuntimeError("[WSClient] Falha ao conectar após todas as tentativas.")

    def _do_connect(self, host: str, port: int, path: str):
        addr = usocket.getaddrinfo(host, port)[0][-1]
        sock = usocket.socket()
        sock.connect(addr)
        sock.settimeout(5)

        key = _ws_handshake_key()
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.send(handshake.encode())

        # Lê resposta HTTP (até linha vazia)
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += sock.recv(1)

        if b"101" not in resp:
            raise RuntimeError(f"WebSocket handshake falhou: {resp[:80]}")

        self._sock = sock

    # ── Send ───────────────────────────────────────────────────
    def send(self, data: dict):
        """Serializa dict para JSON e envia como WebSocket text frame."""
        self._tick()
        data["lamport_ts"] = self._lamport
        payload = ujson.dumps(data).encode()
        self._send_frame(payload)

    def _send_frame(self, payload: bytes):
        length = len(payload)
        mask   = os.urandom(4)
        masked = bytes([payload[i] ^ mask[i % 4] for i in range(length)])

        header = bytearray()
        header.append(0x81)  # FIN + opcode text
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += length.to_bytes(2, 'big')
        header += mask
        self._sock.send(bytes(header) + masked)

    # ── Receive ────────────────────────────────────────────────
    def receive(self) -> dict | None:
        """Recebe o próximo frame WebSocket e retorna o dict JSON."""
        try:
            b0 = self._sock.recv(1)[0]
            b1 = self._sock.recv(1)[0]
            length = b1 & 0x7F
            if length == 126:
                length = int.from_bytes(self._sock.recv(2), 'big')
            elif length == 127:
                length = int.from_bytes(self._sock.recv(8), 'big')

            data = b""
            while len(data) < length:
                chunk = self._sock.recv(length - len(data))
                if not chunk:
                    break
                data += chunk

            msg = ujson.loads(data.decode())
            remote_ts = msg.get("lamport_ts", 0)
            self._update(remote_ts)
            return msg
        except Exception as e:
            print(f"[WSClient] Erro ao receber: {e}")
            return None

    def close(self):
        if self._sock:
            try:
                # Envia close frame
                self._sock.send(b'\x88\x00')
            except:
                pass
            self._sock.close()
            self._sock = None
