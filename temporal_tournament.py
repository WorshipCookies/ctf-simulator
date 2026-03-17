"""
temporal_tournament.py
======================
A drop-in extension of the existing CTF simulator that produces
**longitudinal telemetry** by splitting a full tournament into
configurable match windows (phases).

How it works
------------
- Imports building blocks from the *unmodified* tournament.py and
  ctf_match_simulation_engine.py.
- Generates one canonical match schedule for the entire tournament.
- Iterates through that schedule in windows (e.g. early / mid / late).
- For each window it accumulates telemetry into a fresh PlayerAggregate,
  then serialises the result.
- Produces a long-format CSV:
    PlayerID, PlayerName, Phase, MatchStart, MatchEnd, <all metrics>

Output files
------------
  temporal_dataset.csv        — student-visible longitudinal telemetry
  temporal_ground_truth.csv   — hidden ground truth (one row per player,
                                same format as the original truth CSV)

Usage
-----
  python temporal_tournament.py

All configuration lives in TemporalTournamentConfig below.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Import unmodified building blocks ────────────────────────────────────────
from ctf_match_simulation_engine import (
    CTFMatchSimulation,
    MatchConfig,
    PlayerProfile,
    Role,
    Team,
)
from BehaviorTendency import BehaviorTendency

# Private helpers are still importable in Python; we use them rather than
# copy-pasting their logic.
from tournament import (
    TournamentConfig,
    make_match_schedule,
    generate_ground_truth_attr_perf,
    write_csv,
    _init_aggregates,          # noqa: PLC2701
    _accumulate_match_result,  # noqa: PLC2701
    _finalize_aggregates,      # noqa: PLC2701
)


# ============================================================
# Configuration
# ============================================================

@dataclass
class PhaseSpec:
    """Defines one temporal window within the tournament."""
    name: str           # e.g. "Early", "Mid", "Late"
    start: int          # inclusive match index (0-based)
    end: int            # exclusive match index


@dataclass
class TemporalTournamentConfig:
    """
    Controls the temporal extension.

    phases
        Ordered list of PhaseSpec objects.  Together they must cover
        [0, n_matches).  Gaps are allowed (those matches are run but
        not exported).  Overlaps are NOT recommended.

        Default: three equal thirds of a 1000-match tournament.

    base_tournament_cfg
        Passed through to make_match_schedule / ground-truth generation.
        n_matches here must equal the total number of matches implied by
        all phases combined (or more, if you want trailing matches that
        are not captured in any phase).
    """

    phases: List[PhaseSpec] = field(default_factory=lambda: [
        PhaseSpec("Early", 0,   333),
        PhaseSpec("Mid",   333, 666),
        PhaseSpec("Late",  666, 1000),
    ])

    base_tournament_cfg: TournamentConfig = field(
        default_factory=lambda: TournamentConfig(n_matches=1000)
    )


# ============================================================
# Core runner
# ============================================================

def run_temporal_tournament(
    players: List[PlayerProfile],
    temporal_cfg: Optional[TemporalTournamentConfig] = None,
    match_cfg: Optional[MatchConfig] = None,
    *,
    include_ground_truth: bool = True,
) -> Tuple[List[Dict], Optional[List[Dict]]]:
    """
    Run the full tournament and return per-phase longitudinal rows.

    Returns
    -------
    (temporal_rows, truth_rows)

    temporal_rows
        Long-format list of dicts.  Each dict is one (player, phase) pair
        and contains all standard telemetry columns plus:
            Phase       — phase name  (e.g. "Early")
            MatchStart  — first match index in this phase (1-based for readability)
            MatchEnd    — last match index in this phase (1-based, inclusive)

    truth_rows
        Same format as the original ground-truth CSV.  Based on *full*
        tournament performance.  None if include_ground_truth=False.
    """

    if len(players) < 8:
        raise ValueError("Need at least 8 players to run a 4v4 match.")

    temporal_cfg = temporal_cfg or TemporalTournamentConfig()
    match_cfg    = match_cfg    or MatchConfig()
    t_cfg        = temporal_cfg.base_tournament_cfg

    rng = random.Random(t_cfg.base_seed)

    # ── Build one canonical schedule for the entire tournament ──────────────
    schedule = make_match_schedule(players, t_cfg, rng=rng)
    id_to_player = {p.player_id: p for p in players}

    # ── Prepare per-phase aggregation buckets ───────────────────────────────
    #    phase_agg[phase_name] = {player_id: PlayerAggregate}
    phase_agg: Dict[str, Dict] = {
        spec.name: _init_aggregates(players)
        for spec in temporal_cfg.phases
    }

    # We also keep a global accumulator for ground-truth computation
    global_agg = _init_aggregates(players)

    # ── Build a quick phase lookup: match_index → phase_name (or None) ──────
    index_to_phase: Dict[int, str] = {}
    for spec in temporal_cfg.phases:
        for i in range(spec.start, spec.end):
            index_to_phase[i] = spec.name

    # ── Simulate every match once, route result to the right bucket ─────────
    for match_index, (red_ids, blue_ids) in enumerate(schedule):
        match_seed = t_cfg.base_seed + match_index * t_cfg.seed_stride

        match_players = (
            [id_to_player[pid] for pid in red_ids]
            + [id_to_player[pid] for pid in blue_ids]
        )

        local_match_cfg = MatchConfig(
            **{**match_cfg.__dict__, "randomness_seed": match_seed}
        )

        sim    = CTFMatchSimulation(match_players, config=local_match_cfg)
        result = sim.run()

        kwargs = dict(
            player_rows=result.player_telemetry,
            red_score=result.red_score,
            blue_score=result.blue_score,
        )

        # Accumulate into the appropriate phase bucket (if any)
        phase_name = index_to_phase.get(match_index)
        if phase_name is not None:
            _accumulate_match_result(phase_agg[phase_name], **kwargs)

        # Always accumulate into global (used for ground truth)
        _accumulate_match_result(global_agg, **kwargs)

    # ── Finalise per-phase rows and add Phase / window metadata ─────────────
    temporal_rows: List[Dict] = []

    for spec in temporal_cfg.phases:
        phase_rows = _finalize_aggregates(phase_agg[spec.name])
        for row in phase_rows:
            row["Phase"]      = spec.name
            row["MatchStart"] = spec.start + 1          # 1-based for readability
            row["MatchEnd"]   = spec.end                # last match included
            temporal_rows.append(row)

    # ── Ground truth uses global (full-tournament) performance ──────────────
    truth_rows: Optional[List[Dict]] = None

    if include_ground_truth:
        global_student_rows = _finalize_aggregates(global_agg)
        truth_seed = t_cfg.base_seed + t_cfg.truth_seed_offset
        truth_rows, truth_map = generate_ground_truth_attr_perf(
            players,
            global_student_rows,
            t_cfg,
            seed=truth_seed,
        )

        # Attach hidden truth columns to temporal rows (prefixed with _)
        for row in temporal_rows:
            pid = row["PlayerID"]
            row["_TrueTier"]      = truth_map[pid]["TrueTier"]
            row["_LatentSkill"]   = truth_map[pid]["LatentSkill"]
            row["_PerfScore"]     = truth_map[pid]["PerfScore"]
            row["_CombinedScore"] = truth_map[pid]["CombinedScore"]

    return temporal_rows, truth_rows


# ============================================================
# CSV export
# ============================================================

#: Student-visible columns in the temporal CSV (stable ordering).
TEMPORAL_STUDENT_FIELDS = [
    "PlayerName",
    "PlayerID",
    "PreferredRole",
    "Phase",
    "MatchStart",
    "MatchEnd",
    # Volume counters
    "Matches",
    "Wins",
    "Losses",
    "Draws",
    # Outcome
    "WinRate",
    # Combat
    "Kills",
    "Deaths",
    "KDR",
    "KillsPerMatch",
    "DeathsPerMatch",
    "DuelsWon",
    "DuelsLost",
    # Objective
    "FlagGrabs",
    "Captures",
    "Returns",
    "Interceptions",
    "DefenseStops",
    "ObjectiveActions",
    "GrabsPerMatch",
    "CapturesPerMatch",
    "ReturnsPerMatch",
    "InterceptionsPerMatch",
    "ObjectiveActionsPerMatch",
    # Teamplay / role signals
    "TimeNearCarrier",
    "KillsNearCarrier",
    "KillsWhileCarrierAlive",
    "DefenseStopsNearFlag",
    "ReturnsUnderPressure",
    "FlagRoomPresenceUnderThreat",
    "TimeNearCarrierPerMatch",
    "KillsNearCarrierPerMatch",
    "KillsWhileCarrierAlivePerMatch",
    "DefenseStopsNearFlagPerMatch",
    "ReturnsUnderPressurePerMatch",
    "FlagRoomPresenceUnderThreatPerMatch",
    # Behaviour signal
    "Overextensions",
]

TRUTH_FIELDS = [
    "PlayerName",
    "PlayerID",
    "TrueTier",
    "LatentSkill",
    "PerfScore",
    "CombinedScore",
    "RoleFit",
    "CoreSkill",
    "ConsistencyFactor",
]


def write_temporal_csv(
    temporal_rows: List[Dict],
    truth_rows: Optional[List[Dict]],
    *,
    student_csv_path: str = "temporal_dataset.csv",
    truth_csv_path: str   = "temporal_ground_truth.csv",
) -> None:
    """Write temporal student CSV and (optionally) the truth CSV."""

    # Strip hidden columns for the student export
    student_clean = [
        {k: v for k, v in row.items() if not str(k).startswith("_")}
        for row in temporal_rows
    ]

    # Only keep columns that actually exist in this run
    available = set(student_clean[0].keys()) if student_clean else set()
    fields = [f for f in TEMPORAL_STUDENT_FIELDS if f in available]

    write_csv(student_clean, student_csv_path, fieldnames=fields)
    print(f"  Wrote {len(student_clean)} rows -> {student_csv_path}")

    if truth_rows is not None:
        truth_fields = [f for f in TRUTH_FIELDS if f in truth_rows[0]]
        write_csv(truth_rows, truth_csv_path, fieldnames=truth_fields)
        print(f"  Wrote {len(truth_rows)} rows -> {truth_csv_path}")


# ============================================================
# CLI demo
# ============================================================

if __name__ == "__main__":
    # ── Player pool (identical to the original tournament.py demo) ───────────
    NUM_PLAYERS = 100

    tcfg = TemporalTournamentConfig(
        phases=[
            PhaseSpec("Early", 0,   333),
            PhaseSpec("Mid",   333, 666),
            PhaseSpec("Late",  666, 1000),
        ],
        base_tournament_cfg=TournamentConfig(n_matches=1000),
    )

    tendency_values = [
        BehaviorTendency.OVEREXTENDS_OFTEN,
        BehaviorTendency.TOO_PASSIVE,
        BehaviorTendency.SELFISH_FRAGGER,
        BehaviorTendency.DISCIPLINED_ANCHOR,
        BehaviorTendency.PANIC_UNDER_PRESSURE,
        BehaviorTendency.STRONG_UNDER_OBJECTIVE_PRESSURE,
        BehaviorTendency.INCONSISTENT_HIGH_CEILING,
    ]

    _r = random.Random(tcfg.base_tournament_cfg.base_seed)
    all_players: List[PlayerProfile] = []

    for i in range(NUM_PLAYERS):
        role = [Role.RUNNER, Role.SUPPORT, Role.DEFENDER, Role.MIDFIELD][i % 4]
        all_players.append(
            PlayerProfile(
                player_name=f"P{i + 1}",
                player_id=i + 1,
                aim=_r.randint(20, 95),
                movement=_r.randint(20, 95),
                positioning=_r.randint(20, 95),
                awareness=_r.randint(20, 95),
                teamplay=_r.randint(20, 95),
                decision_making=_r.randint(20, 95),
                consistency=_r.randint(20, 95),
                aggression=_r.randint(20, 95),
                objective_focus=_r.randint(20, 95),
                route_knowledge=_r.randint(20, 95),
                recovery_discipline=_r.randint(20, 95),
                adaptability=_r.randint(20, 95),
                preferred_role=role,
                behavior_tendencies=[tendency_values[i % len(tendency_values)]],
            )
        )

    print(f"Running temporal tournament: {NUM_PLAYERS} players, "
          f"{tcfg.base_tournament_cfg.n_matches} matches, "
          f"{len(tcfg.phases)} phases …")

    temporal_rows, truth_rows = run_temporal_tournament(
        all_players,
        temporal_cfg=tcfg,
        include_ground_truth=True,
    )

    write_temporal_csv(
        temporal_rows,
        truth_rows,
        student_csv_path="temporal_dataset.csv",
        truth_csv_path="temporal_ground_truth.csv",
    )

    # ── Sanity check ─────────────────────────────────────────────────────────
    print("\nSanity check — mean KDR per phase:")
    for phase_name in [s.name for s in tcfg.phases]:
        phase_subset = [r for r in temporal_rows if r["Phase"] == phase_name]
        mean_kdr = sum(r["KDR"] for r in phase_subset) / len(phase_subset)
        print(f"  {phase_name:6s}  mean KDR = {mean_kdr:.3f}  "
              f"(n_player_rows = {len(phase_subset)})")

    if truth_rows:
        tier_order = ["Bronze", "Silver", "Gold", "Diamond"]
        counts = {t: sum(1 for r in truth_rows if r["TrueTier"] == t) for t in tier_order}
        print(f"\nGround truth tier counts: {counts}")