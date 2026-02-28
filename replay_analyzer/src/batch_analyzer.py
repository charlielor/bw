"""Batch analyzer for StarCraft: Brood War replays.

Processes a directory of .rep files, extracts per-player openers,
computes build order signatures, and outputs structured JSON.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from replay_analyzer.src.models import PlayerType, Race
from replay_analyzer.src.replay_parser import ReplayParseError, parse_replay, sort_replays_in_dir
from replay_analyzer.src.signatures import compute_signature


def _race_name(race: Race | int) -> str:
    if isinstance(race, Race):
        return race.name
    return f"RACE_{race}"


def _race_letter(race: Race | int) -> str:
    if isinstance(race, Race):
        return race.name[0]
    return "?"


def _determine_matchup(player_race: Race | int, opponents: list[Race | int]) -> tuple[str, str]:
    """Return (opponent_race_name, matchup_string)."""
    if len(opponents) == 0:
        return "NONE", f"{_race_letter(player_race)}vNone"
    if len(opponents) == 1:
        opp = opponents[0]
        return _race_name(opp), f"{_race_letter(player_race)}v{_race_letter(opp)}"
    return "MULTIPLE", f"{_race_letter(player_race)}vMultiple"


def run_batch_analysis(args: argparse.Namespace) -> None:
    source_dir = Path(args.replay_dir)
    if not source_dir.is_dir():
        print(f"Error: {source_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Sort replays into format subfolders before processing
    if args.verbose:
        print("Sorting replays by format...", file=sys.stderr)
    sort_replays_in_dir(source_dir, verbose=args.verbose)

    rep_files = sorted(source_dir.rglob("*.rep"))
    if not rep_files:
        print(f"No .rep files found in {source_dir}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Found {len(rep_files)} replay files in {source_dir}", file=sys.stderr)

    frame_cutoff = args.frame_cutoff
    min_duration = args.min_duration
    race_filter = args.race.upper() if args.race else None

    openers: list[dict] = []
    errors: list[dict] = []
    parsed_ok = 0

    for rep_path in rep_files:
        if args.verbose:
            print(f"  Parsing {rep_path.name}...", file=sys.stderr)

        try:
            replay = parse_replay(rep_path)
        except (ReplayParseError, Exception) as e:
            errors.append({"file": str(rep_path), "error": str(e)})
            continue

        parsed_ok += 1

        if replay.header.frames < min_duration:
            continue

        active_humans = [
            p for p in replay.header.players
            if p.is_active and p.type in (PlayerType.HUMAN, PlayerType.HUMAN_ALT)
        ]

        for player in active_humans:
            pr = _race_name(player.race)
            if race_filter and pr != race_filter:
                continue

            # Determine opponents
            opponents = [
                p.race for p in active_humans if p.player_id != player.player_id
            ]
            opponent_race, matchup = _determine_matchup(player.race, opponents)

            # Filter build order events for this player within frame cutoff
            player_events = [
                e for e in replay.build_order
                if e.player_id == player.player_id and e.frame <= frame_cutoff
            ]

            if not player_events:
                continue

            signature, event_types = compute_signature(player_events)
            if not signature:
                continue

            game_date = replay.header.start_time.isoformat()

            opener = {
                "replay_file": str(rep_path),
                "map_name": replay.header.map_name,
                "game_date": game_date,
                "game_duration_frames": replay.header.frames,
                "player_name": player.name,
                "player_race": pr,
                "opponent_race": opponent_race,
                "matchup": matchup,
                "events": [
                    {
                        "frame": e.frame,
                        "event_type": e.event_type,
                        "name": e.name,
                    }
                    for e in player_events
                ],
                "signature": signature,
            }
            openers.append(opener)

    # Aggregate by race
    by_race: dict[str, dict] = {}
    for opener in openers:
        race = opener["player_race"]
        if race not in by_race:
            by_race[race] = {"total_openers": 0, "signature_counts": {}}
        by_race[race]["total_openers"] += 1
        sig = opener["signature"]
        by_race[race]["signature_counts"][sig] = (
            by_race[race]["signature_counts"].get(sig, 0) + 1
        )

    # Sort signature counts descending
    for race_data in by_race.values():
        race_data["signature_counts"] = dict(
            sorted(
                race_data["signature_counts"].items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )

    result = {
        "version": "1.0",
        "generated_at": datetime.datetime.now().isoformat(),
        "config": {
            "frame_cutoff": frame_cutoff,
            "min_duration": min_duration,
            "source_directory": str(source_dir),
        },
        "stats": {
            "total_replays": len(rep_files),
            "parsed_ok": parsed_ok,
            "parse_errors": len(errors),
            "total_openers": len(openers),
        },
        "openers": openers,
        "by_race": by_race,
        "errors": errors,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        if args.verbose:
            print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    if args.verbose:
        print(
            f"\nSummary: {parsed_ok}/{len(rep_files)} replays parsed, "
            f"{len(openers)} openers extracted, {len(errors)} errors",
            file=sys.stderr,
        )
        for race, data in sorted(by_race.items()):
            print(f"  {race}: {data['total_openers']} openers", file=sys.stderr)
