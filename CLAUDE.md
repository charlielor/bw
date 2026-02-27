# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

This repository (`bw`) contains a `replay_analyzer` module — a from-scratch binary parser for StarCraft: Brood War `.rep` replay files.

## Running

```bash
uv run python -m replay_analyzer.main <replay.rep>
```

## Architecture

- `replay_analyzer/models.py` — Data models (Replay, Header, Player, enums)
- `replay_analyzer/replay_parser.py` — Binary parser: section reading + decompression + header field extraction
- `replay_analyzer/main.py` — CLI entry point

## Key Dependencies

- `dclimplode` — PKWare DCL Implode decompressor (for legacy replay format)

## Format References

The .rep binary format was reverse-engineered using these sources:
- [screp](https://github.com/icza/screp) by icza — Go replay parser, primary reference for section layout and header field offsets
- [blast.c](https://github.com/madler/zlib/blob/master/contrib/blast) by Mark Adler — PKWare DCL decompressor (used via dclimplode Python bindings)
- [PKWARE DCL Implode](http://justsolve.archiveteam.org/wiki/PKWARE_DCL_Implode) — Archive Team format documentation
- [dclimplode](https://pypi.org/project/dclimplode/) — Python bindings for blast.c and StormLib's implode.c
