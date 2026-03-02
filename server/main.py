"""
Servidor Principal — FastAPI + WebSocket
=========================================
Camadas:
  - Apresentação: Serve arquivos estáticos do frontend (HTML/CSS/JS)
  - API REST: /api/* para lobby, scoreboard, descoberta de serviços
  - WebSocket: /ws/{player_id} — canal de comunicação em tempo real

Concorrência: FastAPI usa asyncio — cada conexão é uma coroutine,
permitindo centenas de clientes simultâneos sem threads bloqueantes.
"""

import asyncio
import json
import os
import socket
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db import database
from game.engine import start_game
from game.game_logger import log_event
from game.models import Player, PlayerStatus
from game.room_manager import room_manager
from middleware.circuit_breaker import db_circuit_breaker
from middleware.lamport_clock import server_clock
from middleware.name_node import name_node

# ─────────────────────────────────────────────
# Inicialização do app
# ─────────────────────────────────────────────
app = FastAPI(title="Jogo da Memória Distribuído", version="1.0.0")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.on_event("startup")
async def startup():
    await database.init_db()
    # Registra este servidor no Nó de Nomes
    local_ip = _get_local_ip()
    name_node.register(
        name="game-server-main",
        ws_url=f"ws://{local_ip}:8000/ws/{{player_id}}",
        http_url=f"http://{local_ip}:8000",
        description="Servidor principal do Jogo da Memória",
    )
    print(f"[Server] Iniciado em http://{local_ip}:8000")
    print(f"[Server] Relógio de Lamport: {server_clock}")
    print(f"[Server] Circuit Breaker DB: {db_circuit_breaker}")


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ─────────────────────────────────────────────
# Páginas HTML
# ─────────────────────────────────────────────
@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/game")
async def game_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "game.html"))

@app.get("/scoreboard")
async def scoreboard_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "scoreboard.html"))


# ─────────────────────────────────────────────
# API REST
# ─────────────────────────────────────────────
@app.get("/api/discover")
async def discover():
    """
    Nó de Nomes: retorna lista de servidores de jogo disponíveis.
    O BitDogLab chama este endpoint ao inicializar para descobrir
    o endereço WebSocket do servidor (transparência de localização).
    """
    name_node.heartbeat("game-server-main")
    services = name_node.list_healthy()
    return JSONResponse({"services": services, "lamport_ts": server_clock.tick()})


@app.get("/api/rooms")
async def list_rooms():
    return JSONResponse({"rooms": room_manager.list_rooms()})


@app.get("/api/scoreboard")
async def get_scoreboard():
    scores = await database.get_scoreboard(limit=20)
    return JSONResponse({"scoreboard": scores})


@app.get("/api/status")
async def status():
    return JSONResponse({
        "server": "online",
        "lamport_clock": server_clock.time,
        "circuit_breaker_db": {
            "state": db_circuit_breaker.state,
            "failures": db_circuit_breaker._failure_count,
        },
        "registered_services": name_node.list_healthy(),
    })


@app.get("/api/log")
async def get_log():
    """
    Retorna o arquivo de log do dia em texto puro (JSON-lines).
    Acesse http://<ip>:8000/api/log para inspecionar ações durante testes.
    """
    import os
    from datetime import datetime
    from fastapi.responses import PlainTextResponse
    log_dir  = os.path.join(os.path.dirname(__file__), "logs")
    log_path = os.path.join(log_dir, f"game_{datetime.now().strftime('%Y%m%d')}.log")
    if not os.path.exists(log_path):
        return PlainTextResponse("Nenhum log encontrado para hoje.")
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


# ─────────────────────────────────────────────
# WebSocket — Canal principal de comunicação
# ─────────────────────────────────────────────
@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    await websocket.accept()

    player = Player(
        id=player_id,
        name=f"Player-{player_id[:4]}",
        websocket=websocket,
    )

    try:
        # Primeira mensagem deve ser de identificação
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        remote_ts = msg.get("lamport_ts", 0)
        server_clock.update(remote_ts)

        if msg.get("type") == "identify":
            player.name = msg.get("name", player.name)[:20]
            player.device_type = msg.get("device_type", "browser")

        await websocket.send_text(json.dumps({
            "type": "identified",
            "player_id": player_id,
            "lamport_ts": server_clock.tick(),
        }))

        # Loop principal de mensagens
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            remote_ts = msg.get("lamport_ts", 0)
            server_clock.update(remote_ts)

            await _handle_message(player, msg, websocket)

    except WebSocketDisconnect:
        print(f"[WS] {player.name} desconectado.")
        room = room_manager.leave_room(player_id)
        if room:
            from game.engine import broadcast_all
            await broadcast_all(room, {
                "type": "player_disconnected",
                "player_id": player_id,
                "player_name": player.name,
                "lamport_ts": server_clock.tick(),
            })
    except asyncio.TimeoutError:
        await websocket.close(code=1001, reason="Timeout de identificação")
    except Exception as e:
        print(f"[WS] Erro inesperado ({player.name}): {e}")
        await websocket.close()


async def _handle_message(player: Player, msg: dict, websocket: WebSocket):
    msg_type = msg.get("type")

    if msg_type == "create_room":
        room = room_manager.create_room(player)
        await websocket.send_text(json.dumps({
            "type": "room_created",
            "room": room.to_dict(),
            "lamport_ts": server_clock.tick(),
        }))

    elif msg_type == "join_room":
        room_id = msg.get("room_id", "").upper()
        try:
            room = room_manager.join_room(room_id, player)
            from game.engine import broadcast_all
            await broadcast_all(room, {
                "type": "player_joined",
                "player": player.to_dict(),
                "room": room.to_dict(),
                "lamport_ts": server_clock.tick(),
            })
        except ValueError as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
                "lamport_ts": server_clock.tick(),
            }))

    elif msg_type == "start_game":
        room = room_manager.get_room_by_player(player.id)
        if not room:
            return
        if room.host_id != player.id:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Apenas o host pode iniciar o jogo.",
                "lamport_ts": server_clock.tick(),
            }))
            return
        if len(room.players) < 2:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Mínimo de 2 jogadores para iniciar.",
                "lamport_ts": server_clock.tick(),
            }))
            return
        # Inicia o jogo em background (não bloqueia o loop de mensagens)
        asyncio.create_task(start_game(room))

    elif msg_type == "restart_game":
        room = room_manager.get_room_by_player(player.id)
        if not room:
            return
        if room.host_id != player.id:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Apenas o host pode reiniciar o jogo.",
                "lamport_ts": server_clock.tick(),
            }))
            return
        try:
            room = room_manager.reset_room(room.id, player.name)
            log_event("room_reset", room.id, {
                "requested_by": player.name,
                "players": [p.name for p in room.players.values()],
            }, server_clock.tick())
            from game.engine import broadcast_all
            await broadcast_all(room, {
                "type": "room_reset",
                "room": room.to_dict(),
                "requested_by": player.name,
                "lamport_ts": server_clock.tick(),
            })
        except ValueError as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
                "lamport_ts": server_clock.tick(),
            }))

    elif msg_type == "ping":
        await websocket.send_text(json.dumps({
            "type": "pong",
            "lamport_ts": server_clock.tick(),
        }))

    elif msg_type == "player_move":
        # Durante o jogo, os moves são tratados pelo engine diretamente
        # via receive_text(). Esta branch só lida com moves fora de turno.
        pass
