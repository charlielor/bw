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
class BuildOrderEvent:
    frame: int
    player_id: int
    event_type: str  # "build", "train", "morph", "building_morph", "tech", "upgrade"
    name: str

    @property
    def timestamp_seconds(self) -> float:
        return self.frame / FRAMES_PER_SECOND

    @property
    def timestamp_display(self) -> str:
        total = int(self.timestamp_seconds)
        minutes, seconds = divmod(total, 60)
        return f"{minutes:02d}:{seconds:02d}"


# Unit ID -> name mapping.
# Reference: https://github.com/icza/screp/blob/main/rep/repcmd/units.go
UNIT_NAMES: dict[int, str] = {
    0x00: "Marine",
    0x01: "Ghost",
    0x02: "Vulture",
    0x03: "Goliath",
    0x05: "Siege Tank (Tank Mode)",
    0x07: "SCV",
    0x08: "Wraith",
    0x09: "Science Vessel",
    0x0B: "Dropship",
    0x0C: "Battlecruiser",
    0x0D: "Spider Mine",
    0x0E: "Nuclear Missile",
    0x1E: "Siege Tank (Siege Mode)",
    0x20: "Firebat",
    0x22: "Medic",
    0x23: "Larva",
    0x24: "Egg",
    0x25: "Zergling",
    0x26: "Hydralisk",
    0x27: "Ultralisk",
    0x29: "Drone",
    0x2A: "Overlord",
    0x2B: "Mutalisk",
    0x2C: "Guardian",
    0x2D: "Queen",
    0x2E: "Defiler",
    0x2F: "Scourge",
    0x32: "Infested Terran",
    0x3A: "Valkyrie",
    0x3B: "Mutalisk Cocoon",
    0x3C: "Corsair",
    0x3D: "Dark Templar",
    0x3E: "Devourer",
    0x3F: "Dark Archon",
    0x40: "Probe",
    0x41: "Zealot",
    0x42: "Dragoon",
    0x43: "High Templar",
    0x44: "Archon",
    0x45: "Shuttle",
    0x46: "Scout",
    0x47: "Arbiter",
    0x48: "Carrier",
    0x49: "Interceptor",
    0x53: "Reaver",
    0x54: "Observer",
    0x55: "Scarab",
    0x61: "Lurker Egg",
    0x67: "Lurker",
    0x6A: "Command Center",
    0x6B: "ComSat",
    0x6C: "Nuclear Silo",
    0x6D: "Supply Depot",
    0x6E: "Refinery",
    0x6F: "Barracks",
    0x70: "Academy",
    0x71: "Factory",
    0x72: "Starport",
    0x73: "Control Tower",
    0x74: "Science Facility",
    0x75: "Covert Ops",
    0x76: "Physics Lab",
    0x78: "Machine Shop",
    0x7A: "Engineering Bay",
    0x7B: "Armory",
    0x7C: "Missile Turret",
    0x7D: "Bunker",
    0x82: "Infested CC",
    0x83: "Hatchery",
    0x84: "Lair",
    0x85: "Hive",
    0x86: "Nydus Canal",
    0x87: "Hydralisk Den",
    0x88: "Defiler Mound",
    0x89: "Greater Spire",
    0x8A: "Queens Nest",
    0x8B: "Evolution Chamber",
    0x8C: "Ultralisk Cavern",
    0x8D: "Spire",
    0x8E: "Spawning Pool",
    0x8F: "Creep Colony",
    0x90: "Spore Colony",
    0x92: "Sunken Colony",
    0x95: "Extractor",
    0x9A: "Nexus",
    0x9B: "Robotics Facility",
    0x9C: "Pylon",
    0x9D: "Assimilator",
    0x9F: "Observatory",
    0xA0: "Gateway",
    0xA2: "Photon Cannon",
    0xA3: "Citadel of Adun",
    0xA4: "Cybernetics Core",
    0xA5: "Templar Archives",
    0xA6: "Forge",
    0xA7: "Stargate",
    0xA9: "Fleet Beacon",
    0xAA: "Arbiter Tribunal",
    0xAB: "Robotics Support Bay",
    0xAC: "Shield Battery",
}

# Tech ID -> name mapping.
# Reference: https://github.com/icza/screp/blob/main/rep/repcmd/techs.go
TECH_NAMES: dict[int, str] = {
    0x00: "Stim Packs",
    0x01: "Lockdown",
    0x02: "EMP Shockwave",
    0x03: "Spider Mines",
    0x04: "Scanner Sweep",
    0x05: "Tank Siege Mode",
    0x06: "Defensive Matrix",
    0x07: "Irradiate",
    0x08: "Yamato Gun",
    0x09: "Cloaking Field",
    0x0A: "Personnel Cloaking",
    0x0B: "Burrowing",
    0x0C: "Infestation",
    0x0D: "Spawn Broodlings",
    0x0E: "Dark Swarm",
    0x0F: "Plague",
    0x10: "Consume",
    0x11: "Ensnare",
    0x12: "Parasite",
    0x13: "Psionic Storm",
    0x14: "Hallucination",
    0x15: "Recall",
    0x16: "Stasis Field",
    0x17: "Archon Warp",
    0x18: "Restoration",
    0x19: "Disruption Web",
    0x1B: "Mind Control",
    0x1C: "Dark Archon Meld",
    0x1D: "Feedback",
    0x1E: "Optical Flare",
    0x1F: "Maelstrom",
    0x20: "Lurker Aspect",
    0x22: "Healing",
}

# Upgrade ID -> name mapping.
# Reference: https://github.com/icza/screp/blob/main/rep/repcmd/upgrades.go
UPGRADE_NAMES: dict[int, str] = {
    0x00: "Terran Infantry Armor",
    0x01: "Terran Vehicle Plating",
    0x02: "Terran Ship Plating",
    0x03: "Zerg Carapace",
    0x04: "Zerg Flyer Carapace",
    0x05: "Protoss Ground Armor",
    0x06: "Protoss Air Armor",
    0x07: "Terran Infantry Weapons",
    0x08: "Terran Vehicle Weapons",
    0x09: "Terran Ship Weapons",
    0x0A: "Zerg Melee Attacks",
    0x0B: "Zerg Missile Attacks",
    0x0C: "Zerg Flyer Attacks",
    0x0D: "Protoss Ground Weapons",
    0x0E: "Protoss Air Weapons",
    0x0F: "Protoss Plasma Shields",
    0x10: "U-238 Shells",
    0x11: "Ion Thrusters",
    0x13: "Titan Reactor",
    0x14: "Ocular Implants",
    0x15: "Moebius Reactor",
    0x16: "Apollo Reactor",
    0x17: "Colossus Reactor",
    0x18: "Ventral Sacs",
    0x19: "Antennae",
    0x1A: "Pneumatized Carapace",
    0x1B: "Metabolic Boost",
    0x1C: "Adrenal Glands",
    0x1D: "Muscular Augments",
    0x1E: "Grooved Spines",
    0x1F: "Gamete Meiosis",
    0x20: "Defiler Energy",
    0x21: "Singularity Charge",
    0x22: "Leg Enhancement",
    0x23: "Scarab Damage",
    0x24: "Reaver Capacity",
    0x25: "Gravitic Drive",
    0x26: "Sensor Array",
    0x27: "Gravitic Booster",
    0x28: "Khaydarin Amulet",
    0x29: "Apial Sensors",
    0x2A: "Gravitic Thrusters",
    0x2B: "Carrier Capacity",
    0x2C: "Khaydarin Core",
    0x2F: "Argus Jewel",
    0x31: "Argus Talisman",
    0x33: "Caduceus Reactor",
    0x34: "Chitinous Plating",
    0x35: "Anabolic Synthesis",
    0x36: "Charon Boosters",
}


@dataclass
class Replay:
    replay_id: bytes
    header: Header
    rep_format: str  # "legacy" or "modern"
    build_order: list[BuildOrderEvent] = field(default_factory=list)
