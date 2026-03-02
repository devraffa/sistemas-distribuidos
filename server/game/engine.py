"""
Game Engine — Lógica Central do Jogo da Memória
------------------------------------------------
Fluxo correto por rodada:
  1. Adiciona UMA nova seta à sequência cumulativa
  2. Exibe a sequência completa para TODOS os jogadores
  3. Apenas o jogador da VEZ deve repetir a sequência inteira
  4. Se errar → eliminado; a sequência continua crescendo
  5. O próximo jogador ativo na ordem circular assume a próxima rodada
  6. Fim quando restar apenas 1 jogador
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
SHOW_ARROW_DURATION = 1.2    # segundos que cada seta fica visível
SEQUENCE_GAP        = 0.4    # pausa entre setas
POST_SEQUENCE_PAUSE = 1.5    # pausa após exibir a sequência
PLAYER_TURN_TIMEOUT = 8.0    # segundos para o jogador responder CADA seta
BETWEEN_ROUNDS_DELAY = 2.5   # pausa entre rodadas


# ─────────────────────────────────────────────────────────────
# Helpers de envio
# ─────────────────────────────────────────────────────────────

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
        print(f"[Engine] Falha ao enviar apos retries: {e}")


async def broadcast_all(room: Room, data: dict):
    """Broadcast para todos os jogadores da sala (ativos + eliminados como espectadores)."""
    tasks = [
        _send(p.websocket, data)
        for p in room.players.values()
        if p.websocket and p.status != PlayerStatus.DISCONNECTED
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


# ─────────────────────────────────────────────────────────────
# Ponto de entrada do jogo
# ─────────────────────────────────────────────────────────────

async def start_game(room: Room):
    if room.status != RoomStatus.LOBBY:
        return

    room.status = RoomStatus.PLAYING
    started_at = time.time()
    game_id = str(uuid.uuid4())

    # Ativa todos os jogadores
    for player in room.players.values():
        if player.status == PlayerStatus.WAITING:
            player.status = PlayerStatus.ACTIVE

    # Define ordem circular de turnos (aleatória)
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


# ─────────────────────────────────────────────────────────────
# Loop principal do jogo
# ─────────────────────────────────────────────────────────────

async def _run_game_loop(room: Room, game_id: str, started_at: float):
    room.current_round = 0
    room.sequence = []          # sequência cumulativa de setas
    turn_ptr = 0                # ponteiro circular na lista de ordem de turnos

    while True:
        active = room.active_players()
        if len(active) <= 1:
            break

        # ── 1. Adiciona UMA nova seta à sequência cumulativa ──────────
        room.current_round += 1
        room.sequence.append(random.choice(DIRECTIONS))

        # ── 2. Seleciona o próximo jogador ativo ──────────────────────
        # Avança o ponteiro até encontrar um jogador ainda ativo
        current_player = None
        for _ in range(len(room.player_turn_order)):
            candidate_id = room.player_turn_order[turn_ptr % len(room.player_turn_order)]
            turn_ptr += 1
            candidate = room.players.get(candidate_id)
            if candidate and candidate.status == PlayerStatus.ACTIVE:
                current_player = candidate
                break

        if current_player is None:
            break

        # ── 3. Anuncia o início da rodada ─────────────────────────────
        await broadcast_all(room, {
            "type": "round_start",
            "round": room.current_round,
            "sequence_length": len(room.sequence),
            "current_player_id": current_player.id,
            "current_player_name": current_player.name,
            "active_count": len(active),
        })

        await asyncio.sleep(0.5)

        # ── 4. Exibe a sequência completa para todos ──────────────────
        await _show_sequence(room)
        await asyncio.sleep(POST_SEQUENCE_PAUSE)

        # ── 5. Coloca o jogador da vez para responder ─────────────────
        await _send(current_player.websocket, {
            "type": "your_turn",
            "sequence_length": len(room.sequence),
            "timeout_ms": int(PLAYER_TURN_TIMEOUT * 1000),
        })

        # Avisa os demais que estão aguardando
        for p in room.players.values():
            if p.websocket and p.id != current_player.id and p.status != PlayerStatus.DISCONNECTED:
                await _send(p.websocket, {
                    "type": "waiting_for_player",
                    "player_id": current_player.id,
                    "player_name": current_player.name,
                    "sequence_length": len(room.sequence),
                })

        # ── 6. Recebe a sequência completa do jogador ─────────────────
        correct = await _collect_player_response(room, current_player)

        # ── 7. Processa resultado ──────────────────────────────────────
        if not correct:
            current_player.status = PlayerStatus.ELIMINATED
            current_player.score = max(0, (room.current_round - 1) * 10)

            await broadcast_all(room, {
                "type": "player_eliminated",
                "player": current_player.to_dict(),
                "round": room.current_round,
            })
        else:
            current_player.rounds_survived += 1
            current_player.score += room.current_round * 10
            await broadcast_all(room, {
                "type": "move_correct",
                "player_id": current_player.id,
                "player_name": current_player.name,
                "round": room.current_round,
            })

        await broadcast_all(room, {
            "type": "round_result",
            "round": room.current_round,
            "player": current_player.to_dict(),
            "correct": correct,
            "survivors": [p.to_dict() for p in room.active_players()],
        })

        await asyncio.sleep(BETWEEN_ROUNDS_DELAY)

    # ── Fim do jogo ────────────────────────────────────────────────────
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

    # Persistência
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


# ─────────────────────────────────────────────────────────────
# Exibição da sequência
# ─────────────────────────────────────────────────────────────

async def _show_sequence(room: Room):
    """Emite as setas da sequência, uma a uma, para todos."""
    await broadcast_all(room, {
        "type": "show_sequence_start",
        "length": len(room.sequence),
    })
    await asyncio.sleep(0.3)

    for i, direction in enumerate(room.sequence):
        await broadcast_all(room, {
            "type": "show_arrow",
            "arrow": direction,
            "position": i + 1,
            "total": len(room.sequence),
        })
        await asyncio.sleep(SHOW_ARROW_DURATION)
        # Limpa a seta antes da próxima
        await broadcast_all(room, {"type": "clear_arrow"})
        await asyncio.sleep(SEQUENCE_GAP)

    await broadcast_all(room, {"type": "show_sequence_end"})


# ─────────────────────────────────────────────────────────────
# Coleta de resposta do jogador
# ─────────────────────────────────────────────────────────────

async def _collect_player_response(room: Room, player: Player) -> bool:
    """
    Recebe do jogador UMA seta por vez, na ordem da sequência.
    Usa Relógio de Lamport para ordenar os eventos recebidos.
    Retorna True se acertou tudo, False se errou ou deu timeout.
    """
    deadline = asyncio.get_event_loop().time() + PLAYER_TURN_TIMEOUT * len(room.sequence)

    try:
        for move_index, expected in enumerate(room.sequence):
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                await _send(player.websocket, {"type": "timeout"})
                return False

            raw = await asyncio.wait_for(
                player.websocket.receive_text(),
                timeout=min(remaining, PLAYER_TURN_TIMEOUT),
            )
            msg = json.loads(raw)

            # Atualiza relógio de Lamport ao receber evento do cliente
            remote_ts = msg.get("lamport_ts", 0)
            server_clock.update(remote_ts)

            if msg.get("type") != "player_move":
                continue  # ignora mensagens fora de contexto

            direction = msg.get("direction", "").upper()

            if direction != expected:
                # Informa erro e para
                await _send(player.websocket, {
                    "type": "move_result",
                    "correct": False,
                    "expected": expected,
                    "got": direction,
                    "move_index": move_index,
                })
                return False
            else:
                await _send(player.websocket, {
                    "type": "move_result",
                    "correct": True,
                    "move_index": move_index,
                    "remaining": len(room.sequence) - move_index - 1,
                })

    except asyncio.TimeoutError:
        await _send(player.websocket, {"type": "timeout"})
        return False
    except Exception as e:
        print(f"[Engine] Erro ao receber de {player.name}: {e}")
        return False

    return True
