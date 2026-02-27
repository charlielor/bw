"""CLI entry point for the BW replay analyzer."""

import sys

from replay_analyzer.replay_parser import ReplayParseError, parse_replay


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <replay.rep>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        replay = parse_replay(path)
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


if __name__ == "__main__":
    main()
