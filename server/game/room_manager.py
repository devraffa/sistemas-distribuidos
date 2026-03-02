"""
Gerenciador de Salas
"""

import uuid
from game.models import Room, Player, RoomStatus, PlayerStatus


class RoomManager:
    def __init__(self):
        self._rooms: dict[str, Room] = {}

    def create_room(self, host: Player) -> Room:
        room_id = str(uuid.uuid4())[:6].upper()
        room = Room(id=room_id, host_id=host.id)
        host.room_id = room_id
        host.is_host = True
        host.status = PlayerStatus.WAITING
        room.players[host.id] = host
        self._rooms[room_id] = room
        print(f"[RoomManager] Sala criada: {room_id} por {host.name}")
        return room

    def join_room(self, room_id: str, player: Player) -> Room:
        room = self._rooms.get(room_id)
        if not room:
            raise ValueError(f"Sala '{room_id}' não encontrada.")
        if room.status != RoomStatus.LOBBY:
            raise ValueError("A partida já começou.")
        if len(room.players) >= 8:
            raise ValueError("Sala cheia (máximo 8 jogadores).")
        player.room_id = room_id
        player.status = PlayerStatus.WAITING
        room.players[player.id] = player
        print(f"[RoomManager] {player.name} entrou na sala {room_id}")
        return room

    def leave_room(self, player_id: str):
        for room in self._rooms.values():
            if player_id in room.players:
                room.players[player_id].status = PlayerStatus.DISCONNECTED
                print(f"[RoomManager] Jogador {player_id} saiu da sala {room.id}")
                return room
        return None

    def get_room(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def get_room_by_player(self, player_id: str) -> Room | None:
        for room in self._rooms.values():
            if player_id in room.players:
                return room
        return None

    def list_rooms(self) -> list[dict]:
        return [
            {
                "id": r.id,
                "player_count": len(r.players),
                "status": r.status,
                "host": r.players[r.host_id].name if r.host_id in r.players else "?",
            }
            for r in self._rooms.values()
            if r.status == RoomStatus.LOBBY
        ]

    def cleanup_empty_rooms(self):
        to_delete = [
            rid for rid, room in self._rooms.items()
            if all(p.status == PlayerStatus.DISCONNECTED for p in room.players.values())
        ]
        for rid in to_delete:
            del self._rooms[rid]
            print(f"[RoomManager] Sala {rid} removida (vazia).")


room_manager = RoomManager()
