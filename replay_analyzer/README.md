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

Output includes game metadata and build orders extracted from the commands section:

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

Build Order — CLBot:
  [2] morph           Drone
  [380] morph           Drone
  [618] morph           Drone
  ...
```

## What replays contain (and don't)

Replay files record **player commands** (intents), not game state. This means:

**What you CAN extract:**
- Build order approximation — "player intended to build X at frame Y"
- APM / action analysis — command frequency, hotkey usage
- Strategic timeline — when tech transitions were initiated

**What you CANNOT extract:**
- Whether a building was canceled or destroyed mid-construction
- Unit deaths from combat
- Current supply / resource counts at a given frame
- Whether a train command actually produced a unit

**Computer AI commands are not recorded.** The replay only captures commands issued through the game client's command buffer — computer AI bypasses this entirely. Games against computer opponents will only show human player actions.

To reconstruct full game state at a given frame, you'd need to simulate the BW engine (e.g. [OpenBW](https://github.com/OpenBW/openbw) or [BWAPI](https://github.com/bwapi/bwapi)).

## Format References

- [screp](https://github.com/icza/screp) by icza — Go replay parser, primary reference for section layout and header field offsets
- [blast.c](https://github.com/madler/zlib/blob/master/contrib/blast) by Mark Adler — PKWare DCL decompressor
- [dclimplode](https://pypi.org/project/dclimplode/) — Python bindings used for legacy replay decompression
