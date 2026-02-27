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

from replay_analyzer.models import (
    GameSpeed,
    GameType,
    Header,
    Player,
    PlayerType,
    Race,
    Replay,
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


class ReplayReader:
    """Reads sections from a .rep binary stream."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0
        self._format = self._detect_format()

    def _detect_format(self) -> str:
        """Detect legacy vs modern format.

        Legacy (pre-1.18): PKWare DCL Implode compression.
        Modern (1.18+): zlib compression, detected by 0x78 at byte 28.

        Reference: https://github.com/icza/screp/blob/main/repparser/repdecoder/repdecoder.go
        """
        if len(self._data) < 30:
            raise ReplayParseError("File too small to be a replay")
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

        if self._format == "modern" and data[0] == 0x78:
            return zlib.decompress(data)

        if self._format == "legacy":
            dec = dclimplode.decompressobj_blast()
            return dec.decompress(data)

        # Modern but not zlib-compressed (raw data)
        return data


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


def parse_replay(path: str | Path) -> Replay:
    """Parse a .rep replay file and return a Replay object.

    Currently parses sections 0 (Replay ID) and 1 (Header).
    Sections 2-4 (Commands, Map Data, Player Names) are skipped.
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

    # Section 1: Header (633 bytes)
    header_data = reader.read_section(SECTION_SIZES[1])
    header = _parse_header(header_data)

    return Replay(
        replay_id=replay_id_data,
        header=header,
        rep_format=reader.format,
    )
