"""
Game Engine — Lógica Central do Jogo da Memória (com Logger integrado)
"""

import asyncio
import json
import random
import time
import uuid

from fastapi import WebSocket

from game.models import Direction, Player, PlayerStatus, Room, RoomStatus
from game.room_manager import room_manager
from game.game_logger import log_event
from middleware.lamport_clock import server_clock
from middleware.retry import retry_with_backoff
from db import database

DIRECTIONS = [Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT]
SHOW_ARROW_DURATION  = 1.2
SEQUENCE_GAP         = 0.4
POST_SEQUENCE_PAUSE  = 1.5
PLAYER_TURN_TIMEOUT  = 8.0
BETWEEN_ROUNDS_DELAY = 2.5


# ─────────────────────────────────────────────────────────────
# Helpers de envio
# ─────────────────────────────────────────────────────────────

async def _send(ws: WebSocket, data: dict):
    ts = server_clock.tick()
    data["lamport_ts"] = ts
    msg = json.dumps(data)
    async def _try():
        await ws.send_text(msg)
    try:
        await retry_with_backoff(coro_factory=_try, max_attempts=3,
                                 base_delay=0.5, exceptions=(Exception,))
    except Exception as e:
        print(f"[Engine] Falha ao enviar apos retries: {e}")


async def broadcast_all(room: Room, data: dict):
    tasks = [
        _send(p.websocket, data)
        for p in room.players.values()
        if p.websocket and p.status != PlayerStatus.DISCONNECTED
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


# ─────────────────────────────────────────────────────────────
# Ponto de entrada
# ─────────────────────────────────────────────────────────────

async def start_game(room: Room):
    if room.status != RoomStatus.LOBBY:
        return

    room.status = RoomStatus.PLAYING
    started_at = time.time()
    game_id = str(uuid.uuid4())

    for player in room.players.values():
        if player.status == PlayerStatus.WAITING:
            player.status = PlayerStatus.ACTIVE

    room.player_turn_order = [
        p.id for p in room.players.values() if p.status == PlayerStatus.ACTIVE
    ]
    random.shuffle(room.player_turn_order)

    log_event("game_started", room.id, {
        "game_id": game_id,
        "players": [p.name for p in room.players.values()],
        "turn_order": [room.players[pid].name for pid in room.player_turn_order],
    }, server_clock.time)

    await broadcast_all(room, {
        "type": "game_started",
        "room": room.to_dict(),
        "turn_order": room.player_turn_order,
        "game_id": game_id,
    })

    await asyncio.sleep(1.5)
    await _run_game_loop(room, game_id, started_at)


# ─────────────────────────────────────────────────────────────
# Loop principal
# ─────────────────────────────────────────────────────────────

async def _run_game_loop(room: Room, game_id: str, started_at: float):
    room.current_round = 0
    room.sequence = []
    turn_ptr = 0

    while True:
        active = room.active_players()
        if len(active) <= 1:
            break

        room.current_round += 1
        room.sequence.append(random.choice(DIRECTIONS))

        # Seleciona próximo jogador ativo (rotação circular)
        current_player = None
        for _ in range(len(room.player_turn_order)):
            cid = room.player_turn_order[turn_ptr % len(room.player_turn_order)]
            turn_ptr += 1
            c = room.players.get(cid)
            if c and c.status == PlayerStatus.ACTIVE:
                current_player = c
                break
        if current_player is None:
            break

        seq_str = " → ".join(room.sequence)
        log_event("round_start", room.id, {
            "round": room.current_round,
            "sequence_length": len(room.sequence),
            "sequence": list(room.sequence),
            "sequence_str": seq_str,
            "current_player_id": current_player.id,
            "current_player_name": current_player.name,
        }, server_clock.time)

        await broadcast_all(room, {
            "type": "round_start",
            "round": room.current_round,
            "sequence_length": len(room.sequence),
            "sequence": list(room.sequence),
            "current_player_id": current_player.id,
            "current_player_name": current_player.name,
            "active_count": len(active),
        })

        await asyncio.sleep(0.5)
        await _show_sequence(room)
        await asyncio.sleep(POST_SEQUENCE_PAUSE)

        await _send(current_player.websocket, {
            "type": "your_turn",
            "sequence_length": len(room.sequence),
            "timeout_ms": int(PLAYER_TURN_TIMEOUT * 1000),
        })

        for p in room.players.values():
            if p.websocket and p.id != current_player.id and p.status != PlayerStatus.DISCONNECTED:
                await _send(p.websocket, {
                    "type": "waiting_for_player",
                    "player_id": current_player.id,
                    "player_name": current_player.name,
                    "sequence_length": len(room.sequence),
                })

        correct = await _collect_player_response(room, current_player, game_id)

        if not correct:
            current_player.status = PlayerStatus.ELIMINATED
            current_player.score = max(0, (room.current_round - 1) * 10)
            log_event("player_eliminated", room.id, {
                "player_id": current_player.id,
                "player_name": current_player.name,
                "round": room.current_round,
                "final_score": current_player.score,
            }, server_clock.time)
            await broadcast_all(room, {
                "type": "player_eliminated",
                "player": current_player.to_dict(),
                "round": room.current_round,
            })
        else:
            current_player.rounds_survived += 1
            current_player.score += room.current_round * 10
            log_event("move_correct", room.id, {
                "player_name": current_player.name,
                "round": room.current_round,
                "score_so_far": current_player.score,
            }, server_clock.time)
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

    # ── Fim do jogo ────────────────────────────────────────────
    room.status = RoomStatus.FINISHED
    active = room.active_players()
    winner = active[0] if active else None

    scoreboard = sorted(
        [p.to_dict() for p in room.players.values()],
        key=lambda x: x["score"], reverse=True,
    )

    log_event("game_over", room.id, {
        "game_id": game_id,
        "winner": winner.name if winner else None,
        "total_rounds": room.current_round,
        "scoreboard": [{
            "name": p["name"],
            "score": p["score"],
            "rounds_survived": p["rounds_survived"],
        } for p in scoreboard],
    }, server_clock.time)

    await broadcast_all(room, {
        "type": "game_over",
        "winner": winner.to_dict() if winner else None,
        "scoreboard": scoreboard,
        "total_rounds": room.current_round,
        "game_id": game_id,
    })

    ended_at = time.time()
    await database.save_game(
        game_id=game_id, room_id=room.id,
        winner_name=winner.name if winner else "N/A",
        total_rounds=room.current_round,
        player_count=len(room.players),
        started_at=started_at, ended_at=ended_at,
    )
    for player in room.players.values():
        await database.save_score(
            game_id=game_id, player_name=player.name,
            rounds_survived=player.rounds_survived,
            score=player.score, device_type=player.device_type,
        )


# ─────────────────────────────────────────────────────────────
# Exibição da sequência
# ─────────────────────────────────────────────────────────────

async def _show_sequence(room: Room):
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
        await broadcast_all(room, {"type": "clear_arrow"})
        await asyncio.sleep(SEQUENCE_GAP)

    await broadcast_all(room, {"type": "show_sequence_end"})


# ─────────────────────────────────────────────────────────────
# Coleta de resposta do jogador (com log de cada move)
# ─────────────────────────────────────────────────────────────

async def _collect_player_response(room: Room, player: Player, game_id: str) -> bool:
    deadline = asyncio.get_event_loop().time() + PLAYER_TURN_TIMEOUT * len(room.sequence)

    try:
        for move_index, expected in enumerate(room.sequence):
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                log_event("player_move", room.id, {
                    "game_id": game_id,
                    "player_id": player.id,
                    "player_name": player.name,
                    "move_index": move_index,
                    "direction": "TIMEOUT",
                    "expected": expected,
                    "correct": False,
                    "round": room.current_round,
                }, server_clock.time)
                await _send(player.websocket, {"type": "timeout"})
                return False

            raw = await asyncio.wait_for(
                player.websocket.receive_text(),
                timeout=min(remaining, PLAYER_TURN_TIMEOUT),
            )
            msg = json.loads(raw)
            remote_ts = msg.get("lamport_ts", 0)
            server_clock.update(remote_ts)

            if msg.get("type") != "player_move":
                continue

            direction = msg.get("direction", "").upper()
            correct = direction == expected

            log_event("player_move", room.id, {
                "game_id": game_id,
                "player_id": player.id,
                "player_name": player.name,
                "move_index": move_index,
                "direction": direction,
                "expected": expected,
                "correct": correct,
                "round": room.current_round,
                "lamport_client": remote_ts,
                "lamport_server": server_clock.time,
            }, server_clock.time)

            if not correct:
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
        log_event("player_move", room.id, {
            "game_id": game_id,
            "player_name": player.name,
            "direction": "TIMEOUT",
            "correct": False,
            "round": room.current_round,
        }, server_clock.time)
        await _send(player.websocket, {"type": "timeout"})
        return False
    except Exception as e:
        print(f"[Engine] Erro ao receber de {player.name}: {e}")
        return False

    return True
