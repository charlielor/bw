# replay analyzer

A from-scratch binary parser for StarCraft: Brood War `.rep` replay files.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Install it if you haven't:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install dependencies:

```bash
uv sync
```

## Usage

```bash
uv run python -m replay_analyzer.main <path-to-replay.rep>
```

Example:

```bash
uv run python -m replay_analyzer.main replay_analyzer/replays/clbot-1.rep
```

Output:

```
Format:    legacy
Map:       Astral Balance (128x96)
Title:     CLBot
Duration:  11m 55s (17036 frames)
Speed:     FASTEST
Type:      FREE_FOR_ALL
Date:      2026-02-26 10:33:45

Players:
  Surtur Brood (ZERG, Computer) - Team 1
  CLBot (ZERG, Human) - Team 1
```

## Format References

- [screp](https://github.com/icza/screp) by icza — Go replay parser, primary reference for section layout and header field offsets
- [blast.c](https://github.com/madler/zlib/blob/master/contrib/blast) by Mark Adler — PKWare DCL decompressor
- [dclimplode](https://pypi.org/project/dclimplode/) — Python bindings used for legacy replay decompression
