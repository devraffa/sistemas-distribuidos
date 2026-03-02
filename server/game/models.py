from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class PlayerStatus(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    ELIMINATED = "eliminated"
    DISCONNECTED = "disconnected"


class RoomStatus(str, Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


@dataclass
class Player:
    id: str
    name: str
    room_id: Optional[str] = None
    status: PlayerStatus = PlayerStatus.WAITING
    websocket: object = field(default=None, repr=False)
    lamport_clock: int = 0
    score: int = 0
    rounds_survived: int = 0
    is_host: bool = False
    device_type: str = "browser"  # "browser" | "bitdoglab"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "room_id": self.room_id,
            "status": self.status,
            "score": self.score,
            "rounds_survived": self.rounds_survived,
            "is_host": self.is_host,
            "device_type": self.device_type,
        }


@dataclass
class Room:
    id: str
    host_id: str
    status: RoomStatus = RoomStatus.LOBBY
    players: dict = field(default_factory=dict)  # player_id -> Player
    current_round: int = 0
    sequence: list = field(default_factory=list)
    current_player_turn_index: int = 0
    player_turn_order: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def active_players(self) -> list:
        return [p for p in self.players.values() if p.status == PlayerStatus.ACTIVE]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "host_id": self.host_id,
            "status": self.status,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "current_round": self.current_round,
            "sequence": self.sequence,
            "player_count": len(self.players),
        }
