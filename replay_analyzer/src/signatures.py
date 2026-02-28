"""Build order signature logic for StarCraft: Brood War replays.

Distills a list of BuildOrderEvents into a short strategic signature string
(e.g. "Depot Rax CC Ebay") for categorizing openers.
"""

from __future__ import annotations

from replay_analyzer.src.models import BuildOrderEvent

# Units to filter out entirely (noise, not strategic decisions).
_FILTERED_UNITS: set[str] = {
    # Workers
    "SCV",
    "Probe",
    "Drone",
    # Intermediate morph states
    "Larva",
    "Egg",
    "Lurker Egg",
    "Mutalisk Cocoon",
    # Auto-produced
    "Interceptor",
    "Scarab",
}

# Supply units: only keep the first occurrence.
_SUPPLY_UNITS: set[str] = {
    "Supply Depot",
    "Pylon",
    "Overlord",
}

# Abbreviation map for readable signatures.
ABBREVIATIONS: dict[str, str] = {
    # Terran buildings
    "Barracks": "Rax",
    "Command Center": "CC",
    "Engineering Bay": "Ebay",
    "Supply Depot": "Depot",
    "Missile Turret": "Turret",
    "Control Tower": "Tower",
    "Science Facility": "SciFac",
    "Covert Ops": "CovertOps",
    "Physics Lab": "PhysLab",
    "Machine Shop": "MShop",
    "Nuclear Silo": "Nuke",
    "Infested CC": "InfCC",
    # Terran units
    "Siege Tank (Tank Mode)": "Tank",
    "Siege Tank (Siege Mode)": "Tank",
    "Science Vessel": "Vessel",
    "Battlecruiser": "BC",
    "Nuclear Missile": "Nuke",
    "Spider Mine": "Mine",
    "Infested Terran": "InfTerran",
    # Protoss buildings
    "Gateway": "Gate",
    "Cybernetics Core": "Core",
    "Robotics Facility": "Robo",
    "Robotics Support Bay": "RoboBay",
    "Citadel of Adun": "Citadel",
    "Templar Archives": "Archives",
    "Arbiter Tribunal": "Tribunal",
    "Fleet Beacon": "Beacon",
    "Photon Cannon": "Cannon",
    "Shield Battery": "Battery",
    # Protoss units
    "Observer": "Obs",
    "High Templar": "HT",
    "Dark Templar": "DT",
    "Dark Archon": "DArch",
    # Zerg buildings
    "Spawning Pool": "Pool",
    "Hatchery": "Hatch",
    "Hydralisk Den": "Den",
    "Evolution Chamber": "Evo",
    "Ultralisk Cavern": "Ultra",
    "Queens Nest": "QNest",
    "Defiler Mound": "DefMound",
    "Greater Spire": "GSpire",
    "Nydus Canal": "Nydus",
    "Creep Colony": "Creep",
    "Spore Colony": "Spore",
    "Sunken Colony": "Sunken",
    # Zerg units
    "Hydralisk": "Hydra",
    "Ultralisk": "Ultra",
    "Mutalisk": "Muta",
    "Guardian": "Guard",
    "Devourer": "Devo",
    # Key upgrades/techs
    "Metabolic Boost": "Speed",
    "Adrenal Glands": "Adrenal",
    "Muscular Augments": "MuscAug",
    "Grooved Spines": "Range",
    "Pneumatized Carapace": "OvlSpeed",
    "Leg Enhancement": "Legs",
    "Singularity Charge": "Goon Range",
    "Lurker Aspect": "Lurker",
    "Stim Packs": "Stim",
    "U-238 Shells": "Range",
    "Tank Siege Mode": "Siege",
    "Spider Mines": "Mines",
    "Ventral Sacs": "VentSacs",
    "Chitinous Plating": "Chitinous",
    "Anabolic Synthesis": "Anabolic",
    "Charon Boosters": "Charon",
    "Ion Thrusters": "Thrusters",
    "Yamato Gun": "Yamato",
    "Cloaking Field": "WCloak",
    "Personnel Cloaking": "GCloak",
    "Psionic Storm": "Storm",
    "Recall": "Recall",
    "Stasis Field": "Stasis",
    "Maelstrom": "Maelstrom",
    "Mind Control": "MC",
    "Disruption Web": "DWeb",
    "Ensnare": "Ensnare",
    "Plague": "Plague",
    "Consume": "Consume",
    "Burrowing": "Burrow",
    "Khaydarin Amulet": "Amulet",
    "Reaver Capacity": "ReavCap",
    "Carrier Capacity": "CarrCap",
    "Scarab Damage": "ScarDmg",
    "Gravitic Drive": "ShuttleSpeed",
    "Gravitic Booster": "ObsSpeed",
    "Gravitic Thrusters": "ScoutSpeed",
    "Apial Sensors": "ApialSens",
}

_MAX_SIGNATURE_ITEMS = 8


def _abbreviate(name: str) -> str:
    return ABBREVIATIONS.get(name, name)


def compute_signature(events: list[BuildOrderEvent]) -> tuple[str, list[str]]:
    """Compute a build order signature from a list of events.

    Returns (signature_string, list_of_abbreviated_names).
    """
    seen_supply = False
    items: list[str] = []
    event_types: list[str] = []

    for event in events:
        if event.name in _FILTERED_UNITS:
            continue

        if event.name in _SUPPLY_UNITS:
            if seen_supply:
                continue
            seen_supply = True

        abbr = _abbreviate(event.name)
        items.append(abbr)
        event_types.append(event.event_type)

    # Truncate to max items
    items = items[:_MAX_SIGNATURE_ITEMS]
    event_types = event_types[:_MAX_SIGNATURE_ITEMS]

    # Collapse consecutive duplicates: ["Gate", "Gate", "Core"] -> ["2x Gate", "Core"]
    collapsed: list[str] = []
    i = 0
    while i < len(items):
        count = 1
        while i + count < len(items) and items[i + count] == items[i]:
            count += 1
        if count > 1:
            collapsed.append(f"{count}x {items[i]}")
        else:
            collapsed.append(items[i])
        i += count

    signature = " ".join(collapsed)
    return signature, event_types
