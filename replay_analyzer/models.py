"""Data models for StarCraft: Brood War replay files.

Format reference: https://github.com/icza/screp (Go replay parser by icza)
Decompression: PKWare DCL Implode via dclimplode (blast.c by Mark Adler)
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import IntEnum


class Race(IntEnum):
    ZERG = 0
    TERRAN = 1
    PROTOSS = 2
    RANDOM = 5

    @classmethod
    def from_id(cls, val: int) -> Race | int:
        try:
            return cls(val)
        except ValueError:
            return val


class PlayerType(IntEnum):
    INACTIVE = 0
    COMPUTER = 1
    HUMAN = 2
    RESCUE_PASSIVE = 3
    OBSERVER = 5
    HUMAN_ALT = 6
    NEUTRAL = 7

    @classmethod
    def from_id(cls, val: int) -> PlayerType | int:
        try:
            return cls(val)
        except ValueError:
            return val


class GameSpeed(IntEnum):
    SLOWEST = 0
    SLOWER = 1
    SLOW = 2
    NORMAL = 3
    FAST = 4
    FASTER = 5
    FASTEST = 6

    @classmethod
    def from_id(cls, val: int) -> GameSpeed | int:
        try:
            return cls(val)
        except ValueError:
            return val


class GameType(IntEnum):
    NONE = 0
    CUSTOM = 1
    MELEE = 2
    FREE_FOR_ALL = 3
    ONE_ON_ONE = 4
    CAPTURE_THE_FLAG = 5
    GREED = 6
    SLAUGHTER = 7
    SUDDEN_DEATH = 8
    LADDER = 9
    USE_MAP_SETTINGS = 10
    TEAM_MELEE = 11
    TEAM_FREE_FOR_ALL = 12
    TEAM_CAPTURE_THE_FLAG = 13
    TOP_VS_BOTTOM = 15

    @classmethod
    def from_id(cls, val: int) -> GameType | int:
        try:
            return cls(val)
        except ValueError:
            return val


# Approximate frames per second in BW engine.
# Reference: https://liquipedia.net/starcraft/Game_Speed
FRAMES_PER_SECOND = 23.81


@dataclass
class Player:
    slot_id: int
    player_id: int
    type: PlayerType | int
    race: Race | int
    team: int
    name: str
    color: int | None = None

    @property
    def is_active(self) -> bool:
        return self.type in (PlayerType.HUMAN, PlayerType.HUMAN_ALT, PlayerType.COMPUTER)


@dataclass
class Header:
    engine: int
    frames: int
    start_time: datetime.datetime
    title: str
    map_width: int
    map_height: int
    speed: GameSpeed | int
    game_type: GameType | int
    sub_type: int
    host: str
    map_name: str
    players: list[Player] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.frames / FRAMES_PER_SECOND

    @property
    def duration_display(self) -> str:
        total = int(self.duration_seconds)
        minutes, seconds = divmod(total, 60)
        return f"{minutes}m {seconds}s"


@dataclass
class Replay:
    replay_id: bytes
    header: Header
    rep_format: str  # "legacy" or "modern"
