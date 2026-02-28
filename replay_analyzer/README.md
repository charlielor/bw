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

### View a single replay

```bash
uv run python -m replay_analyzer.src.main view replay_analyzer/replays/clbot-1.rep
```

The `view` subcommand is optional — passing a `.rep` path directly works too:

```bash
uv run python -m replay_analyzer.src.main replay_analyzer/replays/clbot-1.rep
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

### Batch analyze replays

Process a directory of replays to extract per-race openers with build order signatures:

```bash
uv run python -m replay_analyzer.src.main analyze replay_analyzer/replays/ -v
```

Write results to a JSON file:

```bash
uv run python -m replay_analyzer.src.main analyze replay_analyzer/replays/ -o build_orders.json
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `-o/--output` | stdout | Output JSON path |
| `--frame-cutoff` | 8500 (~6 min) | Max frame for opener window |
| `--min-duration` | 2000 | Skip replays shorter than N frames |
| `--race` | all | Filter to TERRAN, PROTOSS, or ZERG |
| `-v/--verbose` | off | Progress output to stderr |

The output JSON groups openers by race with frequency-counted build order signatures (e.g. `"Depot Rax CC Ebay": 15`), useful as training data for bot development.

### Automatic format sorting

Both `view` and `analyze` automatically detect each replay's format and move it into the correct subfolder before processing:

| Format | Versions | Subfolder |
|--------|----------|-----------|
| Legacy | Pre-1.18 (PKWare DCL compression) | `legacy/` |
| Modern | 1.18–1.20 (zlib compression) | `modern/` |
| Remastered | 1.21+ (zlib, "seRS" magic) | `remastered/` |

For example, a remastered replay sitting in `replays/legacy/` will be moved to `replays/remastered/` automatically. Files already in the correct subfolder are left in place.

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
