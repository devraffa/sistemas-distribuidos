"""
Game Engine — Lógica Central do Jogo da Memória
------------------------------------------------
Controla o ciclo de vida de uma partida:
  1. Iniciar jogo (definir ordem dos players)
  2. Gerar e transmitir sequência crescente de setas
  3. Gerenciar turnos: cada jogador responde na sua vez
  4. Validar respostas com Relógio de Lamport
  5. Eliminar quem errou
  6. Detectar vencedor (último sobrevivente)
  7. Persistir resultados no banco
"""

import asyncio
import json
import random
import time
import uuid

from fastapi import WebSocket

from game.models import Direction, Player, PlayerStatus, Room, RoomStatus
from game.room_manager import room_manager
from middleware.lamport_clock import server_clock
from middleware.retry import retry_with_backoff
from db import database

DIRECTIONS = [Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT]
SHOW_SEQUENCE_DELAY = 1.5   # segundos entre setas ao exibir
PLAYER_TURN_TIMEOUT = 8.0   # segundos para o jogador responder
BETWEEN_ROUNDS_DELAY = 3.0  # pausa entre rodadas


async def _send(ws: WebSocket, data: dict):
    """Envia mensagem JSON via WebSocket com Retry (3 tentativas)."""
    ts = server_clock.tick()
    data["lamport_ts"] = ts
    msg = json.dumps(data)

    async def _try():
        await ws.send_text(msg)

    try:
        await retry_with_backoff(
            coro_factory=_try,
            max_attempts=3,
            base_delay=0.5,
            exceptions=(Exception,),
        )
    except Exception as e:
        print(f"[Engine] Falha ao enviar para WebSocket após retries: {e}")


async def broadcast(room: Room, data: dict, exclude_ids: set = None):
    """Broadcast para todos os jogadores ativos da sala."""
    exclude_ids = exclude_ids or set()
    tasks = [
        _send(p.websocket, data)
        for p in room.players.values()
        if p.websocket and p.status == PlayerStatus.ACTIVE and p.id not in exclude_ids
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def broadcast_all(room: Room, data: dict):
    """Broadcast para TODOS os jogadores da sala (incluindo eliminados — espectadores)."""
    tasks = [
        _send(p.websocket, data)
        for p in room.players.values()
        if p.websocket and p.status != PlayerStatus.DISCONNECTED
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def start_game(room: Room):
    """Inicia a partida na sala dada."""
    if room.status != RoomStatus.LOBBY:
        return

    room.status = RoomStatus.PLAYING
    started_at = time.time()
    game_id = str(uuid.uuid4())

    # Ativa todos os jogadores presentes
    for player in room.players.values():
        if player.status == PlayerStatus.WAITING:
            player.status = PlayerStatus.ACTIVE

    # Define ordem de turnos (aleatória)
    room.player_turn_order = [
        p.id for p in room.players.values() if p.status == PlayerStatus.ACTIVE
    ]
    random.shuffle(room.player_turn_order)

    await broadcast_all(room, {
        "type": "game_started",
        "room": room.to_dict(),
        "turn_order": room.player_turn_order,
    })

    await asyncio.sleep(1.5)
    await _run_game_loop(room, game_id, started_at)


async def _run_game_loop(room: Room, game_id: str, started_at: float):
    room.current_round = 0

    while True:
        active = room.active_players()
        if len(active) <= 1:
            break

        room.current_round += 1
        # Adiciona uma nova seta à sequência
        room.sequence.append(random.choice(DIRECTIONS))

        await broadcast_all(room, {
            "type": "round_start",
            "round": room.current_round,
            "player_count": len(active),
        })

        # Exibe a sequência para todos
        await _show_sequence(room)
        await asyncio.sleep(1.0)

        # Coleta respostas de cada jogador ativo (em turnos)
        eliminated_this_round = []
        for player_id in list(room.player_turn_order):
            player = room.players.get(player_id)
            if not player or player.status != PlayerStatus.ACTIVE:
                continue

            correct = await _collect_player_response(room, player)
            if not correct:
                player.status = PlayerStatus.ELIMINATED
                player.score = max(0, (room.current_round - 1) * 10)
                eliminated_this_round.append(player.to_dict())
                await broadcast_all(room, {
                    "type": "player_eliminated",
                    "player": player.to_dict(),
                    "round": room.current_round,
                })
                await asyncio.sleep(0.5)
            else:
                player.rounds_survived += 1
                player.score += room.current_round * 10

        # Remove eliminados da ordem de turnos
        room.player_turn_order = [
            pid for pid in room.player_turn_order
            if room.players.get(pid) and room.players[pid].status == PlayerStatus.ACTIVE
        ]

        await broadcast_all(room, {
            "type": "round_result",
            "round": room.current_round,
            "eliminated": eliminated_this_round,
            "survivors": [p.to_dict() for p in room.active_players()],
        })

        await asyncio.sleep(BETWEEN_ROUNDS_DELAY)

    # Fim do jogo
    room.status = RoomStatus.FINISHED
    active = room.active_players()
    winner = active[0] if active else None

    scoreboard = sorted(
        [p.to_dict() for p in room.players.values()],
        key=lambda x: x["score"],
        reverse=True,
    )

    await broadcast_all(room, {
        "type": "game_over",
        "winner": winner.to_dict() if winner else None,
        "scoreboard": scoreboard,
        "total_rounds": room.current_round,
    })

    # Persiste no banco de dados
    ended_at = time.time()
    await database.save_game(
        game_id=game_id,
        room_id=room.id,
        winner_name=winner.name if winner else "N/A",
        total_rounds=room.current_round,
        player_count=len(room.players),
        started_at=started_at,
        ended_at=ended_at,
    )
    for player in room.players.values():
        await database.save_score(
            game_id=game_id,
            player_name=player.name,
            rounds_survived=player.rounds_survived,
            score=player.score,
            device_type=player.device_type,
        )


async def _show_sequence(room: Room):
    """Transmite a sequência seta por seta para todos."""
    await broadcast_all(room, {
        "type": "show_sequence_start",
        "length": len(room.sequence),
    })
    await asyncio.sleep(0.5)

    for i, direction in enumerate(room.sequence):
        await broadcast_all(room, {
            "type": "show_arrow",
            "arrow": direction,
            "position": i + 1,
            "total": len(room.sequence),
        })
        await asyncio.sleep(SHOW_SEQUENCE_DELAY)

    await broadcast_all(room, {"type": "show_sequence_end"})


async def _collect_player_response(room: Room, player: Player) -> bool:
    """
    Avisa o jogador que é sua vez, aguarda o movimento do joystick.
    Retorna True se acertou a sequência inteira, False caso contrário.
    """
    await _send(player.websocket, {
        "type": "your_turn",
        "sequence_length": len(room.sequence),
        "timeout_ms": int(PLAYER_TURN_TIMEOUT * 1000),
    })

    # Notifica demais que estão aguardando
    await broadcast(room, {
        "type": "waiting_for_player",
        "player_id": player.id,
        "player_name": player.name,
    }, exclude_ids={player.id})

    # Recebe respostas direction-by-direction
    answers = []
    deadline = asyncio.get_event_loop().time() + PLAYER_TURN_TIMEOUT

    try:
        for expected in room.sequence:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return False

            raw = await asyncio.wait_for(
                player.websocket.receive_text(),
                timeout=remaining,
            )
            msg = json.loads(raw)

            # Atualiza relógio de Lamport ao receber evento do cliente
            remote_ts = msg.get("lamport_ts", 0)
            server_clock.update(remote_ts)

            if msg.get("type") != "player_move":
                return False

            direction = msg.get("direction", "").upper()
            answers.append(direction)

            if direction != expected:
                await _send(player.websocket, {"type": "move_result", "correct": False})
                return False
            else:
                await _send(player.websocket, {"type": "move_result", "correct": True})

    except asyncio.TimeoutError:
        await _send(player.websocket, {"type": "timeout"})
        return False
    except Exception as e:
        print(f"[Engine] Erro ao receber resposta de {player.name}: {e}")
        return False

    return True
