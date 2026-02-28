"""CLI entry point for the BW replay analyzer."""

import argparse
import sys

from replay_analyzer.src.batch_analyzer import run_batch_analysis
from replay_analyzer.src.replay_parser import ReplayParseError, parse_replay, sort_replay_file


def view_replay(args: argparse.Namespace) -> None:
    try:
        new_path = sort_replay_file(args.replay, verbose=True)
        replay = parse_replay(new_path)
    except ReplayParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    h = replay.header
    active_players = [p for p in h.players if p.is_active]

    print(f"Format:    {replay.rep_format}")
    print(f"Map:       {h.map_name} ({h.map_width}x{h.map_height})")
    print(f"Title:     {h.title}")
    print(f"Duration:  {h.duration_display} ({h.frames} frames)")
    print(f"Speed:     {h.speed.name if hasattr(h.speed, 'name') else h.speed}")
    print(f"Type:      {h.game_type.name if hasattr(h.game_type, 'name') else h.game_type}")
    print(f"Date:      {h.start_time}")
    if h.host:
        print(f"Host:      {h.host}")
    print()
    print("Players:")
    for p in active_players:
        race = p.race.name if hasattr(p.race, "name") else f"race_{p.race}"
        ptype = "Human" if p.type in (2, 6) else "Computer"
        print(f"  {p.name} ({race}, {ptype}) - Team {p.team}")

    if replay.build_order:
        player_map = {p.player_id: p.name for p in active_players}
        events_by_player: dict[int, list] = {}
        for event in replay.build_order:
            events_by_player.setdefault(event.player_id, []).append(event)

        for pid in sorted(events_by_player):
            name = player_map.get(pid, f"Player {pid}")
            print(f"\nBuild Order — {name}:")
            for e in events_by_player[pid]:
                print(f"  [{e.frame}] {e.event_type:<15} {e.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="replay_analyzer",
        description="StarCraft: Brood War replay analyzer",
    )
    subparsers = parser.add_subparsers(dest="command")

    # view subcommand
    view_parser = subparsers.add_parser("view", help="View a single replay file")
    view_parser.add_argument("replay", help="Path to .rep replay file")

    # analyze subcommand
    analyze_parser = subparsers.add_parser(
        "analyze", help="Batch analyze replays in a directory"
    )
    analyze_parser.add_argument("replay_dir", help="Directory containing .rep files")
    analyze_parser.add_argument(
        "-o", "--output", help="Output JSON path (default: stdout)"
    )
    analyze_parser.add_argument(
        "--frame-cutoff",
        type=int,
        default=8500,
        help="Max frame for opener window (default: 8500, ~6 min)",
    )
    analyze_parser.add_argument(
        "--min-duration",
        type=int,
        default=2000,
        help="Skip replays shorter than this many frames (default: 2000)",
    )
    analyze_parser.add_argument(
        "--race",
        choices=["TERRAN", "PROTOSS", "ZERG"],
        help="Filter to a specific race",
    )
    analyze_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Progress output to stderr"
    )

    return parser


def main() -> None:
    # Backwards compatibility: if first arg ends in .rep, treat as "view"
    if len(sys.argv) >= 2 and sys.argv[1].endswith(".rep"):
        sys.argv.insert(1, "view")

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "view":
        view_replay(args)
    elif args.command == "analyze":
        run_batch_analysis(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
