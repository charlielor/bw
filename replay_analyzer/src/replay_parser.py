"""Parser for StarCraft: Brood War replay (.rep) files.

Binary format reference: https://github.com/icza/screp by icza
Compression: PKWare DCL Implode, decompressed via dclimplode
  (blast.c by Mark Adler, https://github.com/madler/zlib/blob/master/contrib/blast)
Format details: http://justsolve.archiveteam.org/wiki/PKWARE_DCL_Implode
"""

from __future__ import annotations

import datetime
import struct
import zlib
from pathlib import Path

import dclimplode

from replay_analyzer.src.models import (
    BuildOrderEvent,
    GameSpeed,
    GameType,
    Header,
    Player,
    PlayerType,
    Race,
    Replay,
    TECH_NAMES,
    UNIT_NAMES,
    UPGRADE_NAMES,
)

# Valid replay ID magic bytes.
# Reference: https://github.com/icza/screp/blob/main/repparser/repparser.go
REPLAY_IDS = [b"seRS", b"reRS"]

# Section sizes (0 = dynamic, read size from file).
# Reference: https://github.com/icza/screp/blob/main/repparser/repparser.go
SECTION_SIZES = [
    0x04,   # 0: Replay ID
    0x279,  # 1: Header (633 bytes)
    0,      # 2: Commands (dynamic)
    0,      # 3: Map Data (dynamic)
    0x300,  # 4: Player Names (768 bytes, legacy only)
]


class ReplayParseError(Exception):
    pass


# Map internal format names to directory names.
_FORMAT_DIRS = {
    "legacy": "legacy",
    "modern": "modern",
    "modern121": "remastered",
}


def detect_format(path: str | Path) -> str:
    """Detect replay format without fully parsing.

    Returns "legacy", "modern", or "modern121".
    """
    data = Path(path).read_bytes()
    if len(data) < 30:
        raise ReplayParseError("File too small to be a replay")
    if data[12] == ord("s"):
        return "modern121"
    if data[28] == 0x78:
        return "modern"
    return "legacy"


def sort_replay_file(path: str | Path, verbose: bool = False) -> Path:
    """Sort a single replay into the correct format subfolder.

    Moves the file into legacy/, modern/, or remastered/ under the same
    parent directory. Returns the new path (unchanged if already correct).
    """
    path = Path(path)
    fmt = detect_format(path)
    target_dir_name = _FORMAT_DIRS[fmt]

    # Check if already in the correct subfolder
    if path.parent.name == target_dir_name:
        return path

    target_dir = path.parent / target_dir_name
    # If the file is already inside a format subfolder (wrong one), go up one level
    if path.parent.name in _FORMAT_DIRS.values():
        target_dir = path.parent.parent / target_dir_name

    target_dir.mkdir(exist_ok=True)
    new_path = target_dir / path.name
    if new_path.exists():
        # Avoid overwriting; keep in place
        if verbose:
            import sys
            print(f"  Skipping move, {new_path} already exists", file=sys.stderr)
        return path

    path.rename(new_path)
    if verbose:
        import sys
        print(f"  Sorted {path.name} -> {target_dir_name}/", file=sys.stderr)
    return new_path


def sort_replays_in_dir(directory: str | Path, verbose: bool = False) -> None:
    """Sort all .rep files in a directory tree into format subfolders."""
    directory = Path(directory)
    for rep_path in sorted(directory.rglob("*.rep")):
        try:
            sort_replay_file(rep_path, verbose=verbose)
        except ReplayParseError:
            pass  # Skip files that can't be detected


class ReplayReader:
    """Reads sections from a .rep binary stream."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0
        self._format = self._detect_format()

    def _detect_format(self) -> str:
        """Detect replay format: legacy, modern, or modern121.

        Legacy (pre-1.18): PKWare DCL Implode compression.
        Modern (1.18-1.20): zlib compression, replay ID "reRS".
        Modern121 (1.21+/Remastered): zlib compression, replay ID "seRS",
            extra 4-byte gap between sections 1 and 2.

        Reference: https://github.com/icza/screp/blob/main/repparser/repdecoder/repdecoder.go
        """
        if len(self._data) < 30:
            raise ReplayParseError("File too small to be a replay")
        # Replay ID data sits at offset 12 (after checksum+chunk_count+compressed_len).
        # 's' (0x73) at byte 12 = "seRS" = Modern 1.21+.
        if self._data[12] == ord("s"):
            return "modern121"
        if self._data[28] == 0x78:
            return "modern"
        return "legacy"

    @property
    def format(self) -> str:
        return self._format

    def _read(self, n: int) -> bytes:
        if self._offset + n > len(self._data):
            raise ReplayParseError(
                f"Unexpected end of file at offset 0x{self._offset:x}, "
                f"wanted {n} bytes"
            )
        result = self._data[self._offset : self._offset + n]
        self._offset += n
        return result

    def _read_int32(self) -> int:
        return struct.unpack("<I", self._read(4))[0]

    def read_section(self, expected_size: int) -> bytes:
        """Read and decompress a section.

        Each section has:
          - checksum (4 bytes, ignored)
          - chunk_count (4 bytes)
          - For each chunk:
            - compressed_length (4 bytes)
            - compressed_data (compressed_length bytes)

        Chunks are decompressed and concatenated to produce the section data.

        Reference: https://github.com/icza/screp/blob/main/repparser/repdecoder/repdecoder.go
        """
        _checksum = self._read_int32()
        chunk_count = self._read_int32()

        result = bytearray()
        for _ in range(chunk_count):
            compressed_len = self._read_int32()
            compressed_data = self._read(compressed_len)
            decompressed = self._decompress_chunk(compressed_data)
            result.extend(decompressed)

        return bytes(result)

    def _decompress_chunk(self, data: bytes) -> bytes:
        """Decompress a single chunk based on format."""
        if len(data) <= 4:
            # Too small to be compressed, return as-is
            return data

        if self._format in ("modern", "modern121"):
            # Modern formats use zlib; check per-chunk for 0x78 magic.
            if data[0] == 0x78:
                return zlib.decompress(data)
            return data

        # Legacy: PKWare DCL Implode
        dec = dclimplode.decompressobj_blast()
        return dec.decompress(data)


def _cstring(data: bytes) -> str:
    """Extract a null-terminated string, trying UTF-8 then EUC-KR."""
    null = data.find(b"\x00")
    if null >= 0:
        data = data[:null]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("euc-kr", errors="replace")


def _parse_header(data: bytes) -> Header:
    """Parse the 633-byte header section.

    Field offsets reference:
    https://github.com/icza/screp/blob/main/repparser/repparser.go (parseHeader)
    """
    engine = data[0x00]
    frames = struct.unpack_from("<I", data, 0x01)[0]
    start_unix = struct.unpack_from("<I", data, 0x08)[0]
    start_time = datetime.datetime.fromtimestamp(start_unix)
    title = _cstring(data[0x18 : 0x18 + 28])
    map_width = struct.unpack_from("<H", data, 0x34)[0]
    map_height = struct.unpack_from("<H", data, 0x36)[0]
    speed = GameSpeed.from_id(data[0x3A])
    game_type = GameType.from_id(struct.unpack_from("<H", data, 0x3C)[0])
    sub_type = struct.unpack_from("<H", data, 0x3E)[0]
    host = _cstring(data[0x48 : 0x48 + 24])
    map_name = _cstring(data[0x61 : 0x61 + 26])

    # Parse 12 player slots (36 bytes each) starting at 0xA1.
    players: list[Player] = []
    for i in range(12):
        base = 0xA1 + i * 36
        slot_id = struct.unpack_from("<H", data, base)[0]
        player_id = data[base + 4]
        ptype = PlayerType.from_id(data[base + 8])
        race = Race.from_id(data[base + 9])
        team = data[base + 10]
        name = _cstring(data[base + 11 : base + 36])

        player = Player(
            slot_id=slot_id,
            player_id=player_id,
            type=ptype,
            race=race,
            team=team,
            name=name,
        )

        # Player colors (8 slots, 4 bytes each) at offset 0x251.
        if i < 8:
            player.color = struct.unpack_from("<I", data, 0x251 + i * 4)[0]

        players.append(player)

    return Header(
        engine=engine,
        frames=frames,
        start_time=start_time,
        title=title,
        map_width=map_width,
        map_height=map_height,
        speed=speed,
        game_type=game_type,
        sub_type=sub_type,
        host=host,
        map_name=map_name,
        players=players,
    )


# Command type ID -> param byte count (after the type byte).
# Variable-length commands (select, save/load) handled specially.
# Reference: https://github.com/icza/screp/blob/main/repparser/repparser.go
CMD_PARAM_SIZES: dict[int, int] = {
    0x05: 0,   # KeepAlive
    0x06: -1,  # SaveGame (variable: 4-byte length + data)
    0x07: -1,  # LoadGame (variable: 4-byte length + data)
    0x08: 0,   # RestartGame
    0x09: -2,  # Select (variable: 1 + count*2)
    0x0A: -2,  # SelectAdd (variable: 1 + count*2)
    0x0B: -2,  # SelectRemove (variable: 1 + count*2)
    0x0C: 7,   # Build (order + x + y + unit_id)
    0x0D: 2,   # Vision
    0x0E: 4,   # Alliance
    0x0F: 1,   # GameSpeed
    0x10: 0,   # Pause
    0x11: 0,   # Resume
    0x12: 4,   # Cheat
    0x13: 2,   # Hotkey
    0x14: 9,   # RightClick
    0x15: 10,  # TargetedOrder
    0x18: 0,   # CancelBuild
    0x19: 0,   # CancelMorph
    0x1A: 1,   # Stop (queued byte)
    0x1B: 0,   # CarrierStop
    0x1C: 0,   # ReaverStop
    0x1D: 0,   # OrderNothing
    0x1E: 1,   # ReturnCargo (queued)
    0x1F: 2,   # Train
    0x20: 2,   # CancelTrain
    0x21: 1,   # Cloack (queued)
    0x22: 1,   # Decloack (queued)
    0x23: 2,   # UnitMorph
    0x25: 1,   # Unsiege (queued)
    0x26: 1,   # Siege (queued)
    0x27: 0,   # TrainFighter (interceptor/scarab)
    0x28: 1,   # UnloadAll (queued)
    0x29: 2,   # Unload
    0x2A: 0,   # MergeArchon
    0x2B: 1,   # HoldPosition (queued)
    0x2C: 1,   # Burrow (queued)
    0x2D: 1,   # Unburrow (queued)
    0x2E: 0,   # CancelNuke
    0x2F: 4,   # LiftOff
    0x30: 1,   # Tech
    0x31: 0,   # CancelTech
    0x32: 1,   # Upgrade
    0x33: 0,   # CancelUpgrade
    0x34: 0,   # CancelAddon
    0x35: 2,   # BuildingMorph
    0x36: 0,   # Stim
    0x37: 6,   # Sync
    0x38: 0,   # VoiceEnable
    0x39: 0,   # VoiceDisable
    0x3A: 1,   # VoiceSquelch
    0x3B: 1,   # VoiceUnsquelch
    0x3C: 0,   # StartGame
    0x3D: 1,   # DownloadPercentage
    0x3E: 5,   # ChangeGameSlot
    0x3F: 7,   # NewNetPlayer
    0x40: 17,  # JoinedGame
    0x41: 2,   # ChangeRace
    0x42: 1,   # TeamGameTeam
    0x43: 1,   # UMSTeam
    0x44: 2,   # MeleeTeam
    0x45: 2,   # SwapPlayers
    0x48: 12,  # SavedData
    0x54: 0,   # BriefingStart
    0x55: 1,   # Latency
    0x56: 9,   # ReplaySpeed
    0x57: 1,   # LeaveGame
    0x58: 4,   # MinimapPing
    0x5A: 0,   # MergeDarkArchon
    0x5B: 0,   # MakeGamePublic
    0x5C: 81,  # Chat
    # 1.21+ commands
    0x60: 11,  # RightClick121
    0x61: 12,  # TargetedOrder121
    0x62: 4,   # Unload121
    0x63: -3,  # Select121 (variable: 1 + count*4)
    0x64: -3,  # SelectAdd121 (variable: 1 + count*4)
    0x65: -3,  # SelectRemove121 (variable: 1 + count*4)
}

# Build-order relevant command type IDs.
_BUILD_CMD = 0x0C
_TRAIN_CMD = 0x1F
_UNIT_MORPH_CMD = 0x23
_TECH_CMD = 0x30
_UPGRADE_CMD = 0x32
_BUILDING_MORPH_CMD = 0x35


def _parse_commands(data: bytes) -> list[BuildOrderEvent]:
    """Parse the commands section and extract build-order events.

    Frame block format: frame(4) + block_size(1) + [player_id(1) + type_id(1) + params]*
    Reference: https://github.com/icza/screp/blob/main/repparser/repparser.go
    """
    events: list[BuildOrderEvent] = []
    pos = 0
    size = len(data)

    while pos < size:
        if pos + 5 > size:
            break

        frame = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        block_size = data[pos]
        pos += 1
        block_end = pos + block_size

        while pos < block_end:
            if pos + 2 > block_end:
                pos = block_end
                break

            player_id = data[pos]
            pos += 1
            type_id = data[pos]
            pos += 1

            param_size = CMD_PARAM_SIZES.get(type_id)

            if param_size is None:
                # Unknown command type, skip to end of block
                pos = block_end
                break
            elif param_size == -1:
                # SaveGame/LoadGame: 4-byte length prefix + data
                if pos + 4 > block_end:
                    pos = block_end
                    break
                count = struct.unpack_from("<I", data, pos)[0]
                pos += 4 + count
                continue
            elif param_size == -2:
                # Select variants: 1 byte count + count*2 bytes
                if pos >= block_end:
                    pos = block_end
                    break
                count = data[pos]
                pos += 1 + count * 2
                continue
            elif param_size == -3:
                # Select121 variants: 1 byte count + count*4 bytes
                if pos >= block_end:
                    pos = block_end
                    break
                count = data[pos]
                pos += 1 + count * 4
                continue

            # Extract build-order events before advancing past params
            if type_id == _BUILD_CMD and param_size >= 7:
                # Build: order(1) + x(2) + y(2) + unit_id(2)
                unit_id = struct.unpack_from("<H", data, pos + 5)[0]
                name = UNIT_NAMES.get(unit_id, f"Unknown Unit ({unit_id:#x})")
                events.append(BuildOrderEvent(frame, player_id, "build", name))

            elif type_id == _TRAIN_CMD and param_size >= 2:
                unit_id = struct.unpack_from("<H", data, pos)[0]
                name = UNIT_NAMES.get(unit_id, f"Unknown Unit ({unit_id:#x})")
                events.append(BuildOrderEvent(frame, player_id, "train", name))

            elif type_id == _UNIT_MORPH_CMD and param_size >= 2:
                unit_id = struct.unpack_from("<H", data, pos)[0]
                name = UNIT_NAMES.get(unit_id, f"Unknown Unit ({unit_id:#x})")
                events.append(BuildOrderEvent(frame, player_id, "morph", name))

            elif type_id == _TECH_CMD:
                tech_id = data[pos]
                name = TECH_NAMES.get(tech_id, f"Unknown Tech ({tech_id:#x})")
                events.append(BuildOrderEvent(frame, player_id, "tech", name))

            elif type_id == _UPGRADE_CMD:
                upgrade_id = data[pos]
                name = UPGRADE_NAMES.get(upgrade_id, f"Unknown Upgrade ({upgrade_id:#x})")
                events.append(BuildOrderEvent(frame, player_id, "upgrade", name))

            elif type_id == _BUILDING_MORPH_CMD and param_size >= 2:
                unit_id = struct.unpack_from("<H", data, pos)[0]
                name = UNIT_NAMES.get(unit_id, f"Unknown Unit ({unit_id:#x})")
                events.append(BuildOrderEvent(frame, player_id, "building_morph", name))

            pos += param_size

    events.sort(key=lambda e: e.frame)
    return events


def parse_replay(path: str | Path) -> Replay:
    """Parse a .rep replay file and return a Replay object.

    Parses sections 0 (Replay ID), 1 (Header), and 2 (Commands).
    Sections 3-4 (Map Data, Player Names) are skipped.
    """
    data = Path(path).read_bytes()
    reader = ReplayReader(data)

    # Section 0: Replay ID (4 bytes)
    replay_id_data = reader.read_section(SECTION_SIZES[0])
    if replay_id_data not in REPLAY_IDS:
        raise ReplayParseError(
            f"Not a valid replay file: expected 'reRS' or 'seRS', "
            f"got {replay_id_data!r}"
        )

    # Modern 1.21+ has an extra 4-byte value between sections 0 and 1.
    # Reference: https://github.com/icza/screp/blob/main/repparser/repdecoder/repdecoder.go
    if reader.format == "modern121":
        reader._read_int32()  # skip encoded length

    # Section 1: Header (633 bytes)
    header_data = reader.read_section(SECTION_SIZES[1])
    header = _parse_header(header_data)

    # Section 2: Commands (dynamic size)
    # First read a 4-byte section containing the decompressed size,
    # then read the actual commands section with that size.
    cmd_size_data = reader.read_section(4)
    cmd_decompressed_size = struct.unpack_from("<I", cmd_size_data, 0)[0]
    cmd_data = reader.read_section(cmd_decompressed_size)
    build_order = _parse_commands(cmd_data)

    return Replay(
        replay_id=replay_id_data,
        header=header,
        rep_format=reader.format,
        build_order=build_order,
    )
