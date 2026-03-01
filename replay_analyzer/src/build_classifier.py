"""Build order classifier for StarCraft: Brood War replays.

Classifies openers from build_orders.json into named BW archetype labels
(e.g. "2 Rax", "12 Hatch", "FFE") using rule-based templates on timing landmarks.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from replay_analyzer.src.signatures import _FILTERED_UNITS, _SUPPLY_UNITS, _abbreviate

# Gas buildings per race.
_GAS_BUILDINGS = {"Refinery", "Assimilator", "Extractor"}

# Expand buildings per race.
_EXPAND_BUILDINGS = {"Command Center", "Nexus", "Hatchery"}


def _normalize_events(events: list[dict]) -> list[dict]:
    """Strip workers, intermediates, and duplicate unit types.

    Keep only strategic decision points: buildings, first of each unit type,
    techs, and upgrades.
    """
    seen_unit_types: set[str] = set()
    seen_supply = False
    normalized: list[dict] = []

    for event in events:
        name = event["name"]

        if name in _FILTERED_UNITS:
            continue

        if name in _SUPPLY_UNITS:
            if seen_supply:
                continue
            seen_supply = True

        event_type = event["event_type"]

        # For train/morph units (not buildings/tech/upgrade), only keep first instance
        if event_type in ("train", "morph") and name not in _SUPPLY_UNITS:
            if name in seen_unit_types:
                continue
            seen_unit_types.add(name)

        normalized.append(event)

    return normalized


def _extract_terran_landmarks(events: list[dict]) -> dict[str, Any]:
    """Extract Terran timing landmarks from normalized events."""
    landmarks: dict[str, Any] = {}
    rax_frames: list[int] = []
    gas_frame = None
    expand_frame = None

    for event in events:
        name = event["name"]
        frame = event["frame"]

        if name == "Supply Depot" and "first_depot" not in landmarks:
            landmarks["first_depot"] = frame
        elif name == "Barracks":
            rax_frames.append(frame)
            if "first_rax" not in landmarks:
                landmarks["first_rax"] = frame
        elif name in _GAS_BUILDINGS and gas_frame is None:
            gas_frame = frame
            landmarks["first_gas"] = frame
        elif name == "Command Center" and expand_frame is None:
            expand_frame = frame
            landmarks["first_expand"] = frame
        elif name == "Factory" and "first_factory" not in landmarks:
            landmarks["first_factory"] = frame
        elif name == "Starport" and "first_starport" not in landmarks:
            landmarks["first_starport"] = frame
        elif name == "Engineering Bay" and "first_ebay" not in landmarks:
            landmarks["first_ebay"] = frame
        elif name == "Academy" and "first_academy" not in landmarks:
            landmarks["first_academy"] = frame
        elif name == "Missile Turret" and "first_turret" not in landmarks:
            landmarks["first_turret"] = frame

    # Derived features
    landmarks["rax_count_before_expand"] = (
        len([f for f in rax_frames if f < expand_frame]) if expand_frame else len(rax_frames)
    )
    landmarks["rax_before_gas"] = (
        bool(rax_frames and (gas_frame is None or rax_frames[0] < gas_frame))
    )

    return landmarks


def _extract_zerg_landmarks(events: list[dict]) -> dict[str, Any]:
    """Extract Zerg timing landmarks from normalized events."""
    landmarks: dict[str, Any] = {}
    hatch_frames: list[int] = []
    pool_frame = None
    overlord_frame = None

    for event in events:
        name = event["name"]
        frame = event["frame"]

        if name == "Overlord" and overlord_frame is None:
            overlord_frame = frame
            landmarks["first_overlord"] = frame
        elif name == "Spawning Pool" and pool_frame is None:
            pool_frame = frame
            landmarks["first_pool"] = frame
        elif name == "Hatchery":
            hatch_frames.append(frame)
            if "first_hatch" not in landmarks:
                landmarks["first_hatch"] = frame
        elif name in _GAS_BUILDINGS and "first_gas" not in landmarks:
            landmarks["first_gas"] = frame
        elif name == "Lair" and "first_lair" not in landmarks:
            landmarks["first_lair"] = frame
        elif name == "Hydralisk Den" and "first_den" not in landmarks:
            landmarks["first_den"] = frame
        elif name == "Spire" and "first_spire" not in landmarks:
            landmarks["first_spire"] = frame
        elif name == "Evolution Chamber" and "first_evo" not in landmarks:
            landmarks["first_evo"] = frame
        elif name == "Sunken Colony" and "first_sunken" not in landmarks:
            landmarks["first_sunken"] = frame

    # Derived features
    landmarks["pool_before_hatch"] = bool(
        pool_frame is not None and (not hatch_frames or pool_frame < hatch_frames[0])
    )
    landmarks["pool_before_overlord"] = bool(
        pool_frame is not None and overlord_frame is not None and pool_frame < overlord_frame
    )
    landmarks["hatch_count_before_pool"] = (
        len([f for f in hatch_frames if f < pool_frame]) if pool_frame else len(hatch_frames)
    )

    # Pool timing category based on frame (rough supply proxy)
    # Early pools happen before ~1500 frames, standard 1500-3000, late >3000
    if pool_frame is not None:
        if pool_frame < 1500:
            landmarks["pool_timing_category"] = "early"
        elif pool_frame <= 3000:
            landmarks["pool_timing_category"] = "standard"
        else:
            landmarks["pool_timing_category"] = "late"

    return landmarks


def _extract_protoss_landmarks(events: list[dict]) -> dict[str, Any]:
    """Extract Protoss timing landmarks from normalized events."""
    landmarks: dict[str, Any] = {}
    gate_frames: list[int] = []
    gas_frame = None
    forge_frame = None
    nexus_frame = None

    for event in events:
        name = event["name"]
        frame = event["frame"]

        if name == "Pylon" and "first_pylon" not in landmarks:
            landmarks["first_pylon"] = frame
        elif name == "Gateway":
            gate_frames.append(frame)
            if "first_gate" not in landmarks:
                landmarks["first_gate"] = frame
        elif name in _GAS_BUILDINGS and gas_frame is None:
            gas_frame = frame
            landmarks["first_gas"] = frame
        elif name == "Cybernetics Core" and "first_core" not in landmarks:
            landmarks["first_core"] = frame
        elif name == "Nexus" and nexus_frame is None:
            nexus_frame = frame
            landmarks["first_nexus"] = frame
        elif name == "Forge" and forge_frame is None:
            forge_frame = frame
            landmarks["first_forge"] = frame
        elif name == "Photon Cannon" and "first_cannon" not in landmarks:
            landmarks["first_cannon"] = frame
        elif name == "Citadel of Adun" and "first_citadel" not in landmarks:
            landmarks["first_citadel"] = frame
        elif name == "Templar Archives" and "first_archives" not in landmarks:
            landmarks["first_archives"] = frame
        elif name == "Robotics Facility" and "first_robo" not in landmarks:
            landmarks["first_robo"] = frame
        elif name == "Stargate" and "first_stargate" not in landmarks:
            landmarks["first_stargate"] = frame

    # Derived features
    core_frame = landmarks.get("first_core")
    landmarks["gates_before_tech"] = len(
        [f for f in gate_frames if f < core_frame] if core_frame else gate_frames
    )
    landmarks["forge_before_gate"] = bool(
        forge_frame is not None and (not gate_frames or forge_frame < gate_frames[0])
    )

    return landmarks


def _classify_terran(landmarks: dict[str, Any]) -> tuple[str, str]:
    """Classify a Terran opener. Returns (archetype, confidence)."""
    first_depot = landmarks.get("first_depot")
    first_rax = landmarks.get("first_rax")
    first_gas = landmarks.get("first_gas")
    first_expand = landmarks.get("first_expand")
    first_factory = landmarks.get("first_factory")
    first_ebay = landmarks.get("first_ebay")
    first_turret = landmarks.get("first_turret")
    rax_before_expand = landmarks.get("rax_count_before_expand", 0)
    rax_before_gas = landmarks.get("rax_before_gas", False)

    if not first_rax:
        return "Unknown", "low"

    # BBS: 2+ Rax before Depot or very early 2nd Rax (before depot finishes)
    if first_depot and rax_before_expand >= 2 and first_rax < first_depot:
        return "BBS", "high"

    # Sim City / Turtle: Early Ebay + Turrets
    if first_ebay and first_turret:
        if first_ebay < (first_factory or float("inf")):
            if not first_expand or first_turret < first_expand:
                return "Sim City / Turtle", "medium"

    # 1 Rax FE: 1 Rax → CC before 2nd Rax
    if first_expand and rax_before_expand == 1:
        if not first_gas or first_expand < first_gas or first_expand < (first_factory or float("inf")):
            return "1 Rax FE", "high"

    # 2 Rax: 2 Rax before gas/expand
    if rax_before_expand >= 2 and rax_before_gas:
        if not first_gas or (first_gas > first_rax):
            return "2 Rax", "high"

    # 1 Rax Gas → Factory: Rax → Refinery → Factory
    if first_gas and first_factory:
        if first_rax < first_gas < first_factory:
            return "1 Rax Gas → Factory", "high"

    # Fallback: if we have rax + gas but no factory yet, still could be 1 rax gas
    if first_rax and first_gas and rax_before_gas:
        if not first_expand or first_gas < first_expand:
            if first_factory:
                return "1 Rax Gas → Factory", "medium"

    # 2 Rax fallback: if 2 rax counted at all
    if rax_before_expand >= 2:
        return "2 Rax", "medium"

    return "Unknown", "low"


def _classify_zerg(landmarks: dict[str, Any]) -> tuple[str, str]:
    """Classify a Zerg opener. Returns (archetype, confidence)."""
    pool_frame = landmarks.get("first_pool")
    hatch_frame = landmarks.get("first_hatch")
    overlord_frame = landmarks.get("first_overlord")
    first_gas = landmarks.get("first_gas")
    first_lair = landmarks.get("first_lair")
    first_spire = landmarks.get("first_spire")
    pool_before_hatch = landmarks.get("pool_before_hatch", False)
    pool_before_overlord = landmarks.get("pool_before_overlord", False)
    hatch_count_before_pool = landmarks.get("hatch_count_before_pool", 0)
    pool_timing = landmarks.get("pool_timing_category", "standard")

    if not pool_frame:
        return "Unknown", "low"

    # 4/5 Pool: Pool before Overlord (extremely aggressive)
    if pool_before_overlord:
        return "4/5 Pool", "high"

    # 3 Hatch: 2+ Hatch before Pool or gas (greedy macro)
    if hatch_count_before_pool >= 2:
        return "3 Hatch", "high"

    # 12 Hatch: Hatch before Pool
    if hatch_frame and not pool_before_hatch:
        return "12 Hatch", "high"

    # Muta Build: Lair → Spire path
    if first_lair and first_spire:
        return "Muta Build", "medium"

    # 9 Pool: Pool early, before Hatch
    if pool_before_hatch and pool_timing == "early":
        return "9 Pool", "high"

    # Overpool: Overlord → Pool → Hatch (standard order)
    if pool_before_hatch and overlord_frame and overlord_frame < pool_frame:
        return "Overpool", "high"

    # Fallback based on pool timing
    if pool_before_hatch:
        if pool_timing == "standard":
            return "Overpool", "medium"
        return "9 Pool", "medium"

    return "Unknown", "low"


def _classify_protoss(landmarks: dict[str, Any]) -> tuple[str, str]:
    """Classify a Protoss opener. Returns (archetype, confidence)."""
    first_gate = landmarks.get("first_gate")
    first_gas = landmarks.get("first_gas")
    first_core = landmarks.get("first_core")
    first_nexus = landmarks.get("first_nexus")
    first_forge = landmarks.get("first_forge")
    first_cannon = landmarks.get("first_cannon")
    first_citadel = landmarks.get("first_citadel")
    first_archives = landmarks.get("first_archives")
    gates_before_tech = landmarks.get("gates_before_tech", 0)
    forge_before_gate = landmarks.get("forge_before_gate", False)

    if not first_gate and not first_forge:
        return "Unknown", "low"

    # FFE (Forge FE): Forge → Cannon → Nexus
    if forge_before_gate and first_forge and first_cannon:
        if first_nexus and first_nexus < (first_core or float("inf")):
            return "FFE (Forge FE)", "high"
        # Forge + Cannon without nexus yet but forge is first
        return "FFE (Forge FE)", "medium"

    # FE (Nexus First): Nexus before or right after Gate
    if first_nexus and first_gate:
        # Nexus before gate, or nexus very soon after gate (within ~1000 frames)
        if first_nexus <= first_gate or (first_nexus - first_gate < 1000 and not first_core):
            return "FE (Nexus First)", "high"
        # Nexus before core
        if first_core and first_nexus < first_core:
            return "FE (Nexus First)", "medium"

    # DT Rush: Gate → Core → Citadel → Archives
    if first_citadel and first_archives:
        if first_gate and first_core:
            if first_gate < first_core < first_citadel < first_archives:
                # DT rush if archives comes relatively early and no expansion
                if not first_nexus or first_archives < first_nexus:
                    return "DT Rush", "high"
                return "DT Rush", "medium"

    # 2 Gate: 2 Gates before gas/tech
    if gates_before_tech >= 2:
        if not first_gas or (first_gate and first_gas > first_gate):
            return "2 Gate", "high"
        return "2 Gate", "medium"

    # 1 Gate Core: Gate → Gas → Core (standard opening)
    if first_gate and first_gas and first_core:
        if first_gate < first_gas and first_gas <= first_core:
            return "1 Gate Core", "high"
        # Gate and core present, close enough
        if first_gate < first_core:
            return "1 Gate Core", "medium"

    # Fallback: single gate with core
    if first_gate and first_core:
        return "1 Gate Core", "medium"

    # Single gate, no tech yet
    if first_gate:
        return "Unknown", "low"

    return "Unknown", "low"


def classify_opener(opener: dict) -> dict:
    """Classify a single opener from build_orders.json into an archetype.

    Returns a classified opener dict with archetype, confidence, landmarks,
    and normalized sequence.
    """
    race = opener["player_race"]
    events = opener["events"]

    # Normalize
    normalized = _normalize_events(events)
    normalized_names = [_abbreviate(e["name"]) for e in normalized]

    # Extract landmarks and classify
    if race == "TERRAN":
        landmarks = _extract_terran_landmarks(events)
        archetype, confidence = _classify_terran(landmarks)
    elif race == "ZERG":
        landmarks = _extract_zerg_landmarks(events)
        archetype, confidence = _classify_zerg(landmarks)
    elif race == "PROTOSS":
        landmarks = _extract_protoss_landmarks(events)
        archetype, confidence = _classify_protoss(landmarks)
    else:
        landmarks = {}
        archetype, confidence = "Unknown", "low"

    # Compute signature from normalized events (reuse signatures logic)
    from replay_analyzer.src.signatures import compute_signature
    from replay_analyzer.src.models import BuildOrderEvent

    build_events = [
        BuildOrderEvent(
            frame=e["frame"],
            player_id=0,
            event_type=e["event_type"],
            name=e["name"],
        )
        for e in events
    ]
    signature, _ = compute_signature(build_events)

    return {
        "replay_file": opener["replay_file"],
        "player_name": opener["player_name"],
        "player_race": race,
        "matchup": opener["matchup"],
        "archetype": archetype,
        "confidence": confidence,
        "landmarks": landmarks,
        "signature": signature,
        "normalized_sequence": normalized_names,
    }


def classify_build_orders(input_path: Path) -> dict:
    """Load build_orders.json and classify all openers.

    Returns the full classified output dict.
    """
    data = json.loads(input_path.read_text(encoding="utf-8"))
    openers = data.get("openers", [])

    classified: list[dict] = []
    for opener in openers:
        classified.append(classify_opener(opener))

    # Build summary: race → archetype → count
    summary: dict[str, dict[str, int]] = {}
    for entry in classified:
        race = entry["player_race"]
        archetype = entry["archetype"]
        if race not in summary:
            summary[race] = {}
        summary[race][archetype] = summary[race].get(archetype, 0) + 1

    # Sort archetype counts descending within each race
    for race in summary:
        summary[race] = dict(
            sorted(summary[race].items(), key=lambda x: x[1], reverse=True)
        )

    return {
        "version": "1.0",
        "generated_at": datetime.datetime.now().isoformat(),
        "source_file": str(input_path),
        "classified_openers": classified,
        "summary": summary,
    }
