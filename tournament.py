from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional, Tuple
import csv
import math
import random

# Assumes these are importable from your simulator package/module
# If you keep everything in one file, replace imports accordingly.
from ctf_match_simulation_engine import (
    CTFMatchSimulation,
    MatchConfig,
    PlayerProfile,
    Role,
    Team,
)

from BehaviorTendency import BehaviorTendency

# ============================================================
# Config
# ============================================================

@dataclass
class TournamentConfig:
    """Controls how a tournament (batch of matches) is generated and aggregated."""

    n_matches: int = 1000
    base_seed: int = 123

    # Matchmaking
    matchmaking: str = "role_balanced"  # "random" | "role_balanced" | "skill_balanced" (stub)

    # Ensures each match uses a unique deterministic seed derived from base_seed
    seed_stride: int = 10_000

    # Controls how many times we will try to find a role-balanced split for a sampled set of 8
    max_role_balance_attempts: int = 25

    # If True, the tournament will try to ensure each player appears roughly equally.
    # If False, matches are sampled independently (some players may appear more).
    round_robinish: bool = True

    # Ground truth generation
    truth_seed_offset: int = 9_999

    # Default tier split (must sum to 1.0)
    tier_distribution: Tuple[float, float, float, float] = (0.40, 0.35, 0.20, 0.05)  # Bronze, Silver, Gold, Diamond


# ============================================================
# Public API
# ============================================================

def run_tournament(
    players: List[PlayerProfile],
    tournament_cfg: Optional[TournamentConfig] = None,
    match_cfg: Optional[MatchConfig] = None,
    *,
    include_ground_truth: bool = True,
) -> Tuple[List[Dict], Optional[List[Dict]]]:
    """Runs a batch of 4v4 matches.

    Returns:
        (student_rows, truth_rows)

        - student_rows: per-player aggregated telemetry (no ground truth)
        - truth_rows: per-player ground-truth tier table (PlayerID, TrueTier, LatentSkill, ...)
          If include_ground_truth=False, truth_rows is None.
    """

    if len(players) < 8:
        raise ValueError("Need at least 8 players to run a 4v4 match.")

    tournament_cfg = tournament_cfg or TournamentConfig()
    match_cfg = match_cfg or MatchConfig()

    rng = random.Random(tournament_cfg.base_seed)

    # Initialize aggregation structures
    agg: Dict[int, Dict] = _init_aggregates(players)

    # Create match schedule (list of (team_red_ids, team_blue_ids))
    schedule = make_match_schedule(players, tournament_cfg, rng=rng)

    for match_index, (red_ids, blue_ids) in enumerate(schedule):
        match_seed = tournament_cfg.base_seed + match_index * tournament_cfg.seed_stride

        # Build 8-player list in team order: first 4 red, then 4 blue
        id_to_player = {p.player_id: p for p in players}
        match_players = [id_to_player[pid] for pid in red_ids] + [id_to_player[pid] for pid in blue_ids]

        # Per-match determinism via seed.
        local_match_cfg = MatchConfig(**{**match_cfg.__dict__, "randomness_seed": match_seed})

        sim = CTFMatchSimulation(match_players, config=local_match_cfg)
        result = sim.run()

        _accumulate_match_result(agg, result.player_telemetry, red_score=result.red_score, blue_score=result.blue_score)

    student_rows = _finalize_aggregates(agg)
    
    truth_rows: Optional[List[Dict]] = None
    truth_map: Optional[Dict[int, Dict]] = None

    if include_ground_truth:
        truth_seed = tournament_cfg.base_seed + tournament_cfg.truth_seed_offset
        truth_rows, truth_map = generate_ground_truth_attr_perf(
            players,
            student_rows,
            tournament_cfg,
            seed=truth_seed,
        )

    # Optional: attach truth internally (NOT for student export) if you want convenience
    # We keep student_rows clean by default.
    if truth_map is not None:
        for r in student_rows:
            pid = r["PlayerID"]
            r["_TrueTier"] = truth_map[pid]["TrueTier"]
            r["_LatentSkill"] = truth_map[pid]["LatentSkill"]
            r["_PerfScore"] = truth_map[pid]["PerfScore"]
            r["_CombinedScore"] = truth_map[pid]["CombinedScore"]

    return student_rows, truth_rows


def write_csv(rows: List[Dict], filepath: str, *, fieldnames: Optional[List[str]] = None) -> None:
    """Write list-of-dicts to CSV with stable column order."""

    if not rows:
        raise ValueError("No rows to write.")

    if fieldnames is None:
        # Use keys from first row; keep consistent order
        fieldnames = list(rows[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_student_and_truth_csv(
    student_rows: List[Dict],
    truth_rows: List[Dict],
    *,
    student_csv_path: str,
    truth_csv_path: str,
) -> None:
    """Convenience helper: writes both student and truth CSVs.

    Student CSV excludes any keys beginning with '_' by convention.
    """

    student_clean = [
        {k: v for k, v in r.items() if not str(k).startswith("_")}
        for r in student_rows
    ]

    # Student columns: stable and explicit (so the assignment stays consistent)
    student_fields = [
        "PlayerName",
        "PlayerID",
        "PreferredRole",
        "Matches",
        "Wins",
        "Losses",
        "Draws",
        "WinRate",
        "Kills",
        "Deaths",
        "KDR",
        "KillsPerMatch",
        "DeathsPerMatch",
        "DuelsWon",
        "DuelsLost",
        "FlagGrabs",
        "Captures",
        "Returns",
        "Interceptions",
        "DefenseStops",
        "Overextensions",
        "ObjectiveActions",
        "GrabsPerMatch",
        "CapturesPerMatch",
        "ReturnsPerMatch",
        "InterceptionsPerMatch",
        "ObjectiveActionsPerMatch",
        "TimeNearCarrier",
        "KillsWhileCarrierAlive",
        "DefenseStopsNearFlag",
        "ReturnsUnderPressure",
        "TimeNearCarrierPerMatch",
        "KillsWhileCarrierAlivePerMatch",
        "DefenseStopsNearFlagPerMatch",
        "ReturnsUnderPressurePerMatch",
        "FlagRoomPresenceUnderThreat",
        "FlagRoomPresenceUnderThreatPerMatch",
        "KillsNearCarrier",
        "KillsNearCarrierPerMatch",
    ]

    # Only include columns that actually exist (in case you tweak telemetry)
    student_fields = [c for c in student_fields if c in student_clean[0]]

    truth_fields = [
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

    write_csv(student_clean, student_csv_path, fieldnames=student_fields)
    write_csv(truth_rows, truth_csv_path, fieldnames=truth_fields)


# ============================================================
# Match schedule
# ============================================================

def make_match_schedule(
    players: List[PlayerProfile],
    cfg: TournamentConfig,
    rng: Optional[random.Random] = None,
) -> List[Tuple[List[int], List[int]]]:
    """Produces a schedule of matches.

    Each item: (red_player_ids[4], blue_player_ids[4]).
    """

    rng = rng or random.Random(cfg.base_seed)
    player_ids = [p.player_id for p in players]

    schedule: List[Tuple[List[int], List[int]]] = []

    if cfg.round_robinish:
        # Roughly equalize participation:
        # shuffle, then consume in chunks of 8, reshuffle when exhausted.
        bag = player_ids[:]
        rng.shuffle(bag)

        for _ in range(cfg.n_matches):
            if len(bag) < 8:
                bag = player_ids[:]
                rng.shuffle(bag)
            sample = [bag.pop() for _ in range(8)]
            red_ids, blue_ids = _split_into_teams(sample, players, cfg, rng)
            schedule.append((red_ids, blue_ids))
    else:
        for _ in range(cfg.n_matches):
            sample = rng.sample(player_ids, 8)
            red_ids, blue_ids = _split_into_teams(sample, players, cfg, rng)
            schedule.append((red_ids, blue_ids))

    return schedule


# ============================================================
# Team splitting strategies
# ============================================================

def _split_into_teams(
    sample_ids: List[int],
    players: List[PlayerProfile],
    cfg: TournamentConfig,
    rng: random.Random,
) -> Tuple[List[int], List[int]]:
    id_to_player = {p.player_id: p for p in players}

    if cfg.matchmaking == "random":
        rng.shuffle(sample_ids)
        return sample_ids[:4], sample_ids[4:]

    if cfg.matchmaking == "role_balanced":
        best = None
        best_score = float("inf")

        # Try a few random splits; keep the most role-balanced one.
        for _ in range(cfg.max_role_balance_attempts):
            ids = sample_ids[:]
            rng.shuffle(ids)
            red = ids[:4]
            blue = ids[4:]
            score = _role_balance_cost([id_to_player[i] for i in red]) + _role_balance_cost([id_to_player[i] for i in blue])
            if score < best_score:
                best_score = score
                best = (red, blue)
                if best_score == 0:
                    break

        assert best is not None
        return best

    if cfg.matchmaking == "skill_balanced":
        # Stub: you can later balance by hidden truth / latent skill.
        rng.shuffle(sample_ids)
        return sample_ids[:4], sample_ids[4:]

    raise ValueError(f"Unknown matchmaking mode: {cfg.matchmaking}")


def _role_balance_cost(team: List[PlayerProfile]) -> int:
    """Lower is better. 0 means the team covers all four preferred roles."""

    present = {p.preferred_role for p in team}
    missing = {Role.RUNNER, Role.SUPPORT, Role.DEFENDER, Role.MIDFIELD} - present
    return len(missing)


# ============================================================
# Ground truth tier generation
# ============================================================

_TIER_NAMES = ("Bronze", "Silver", "Gold", "Diamond")


def generate_ground_truth(
    players: List[PlayerProfile],
    cfg: TournamentConfig,
    *,
    seed: int,
) -> Tuple[List[Dict], Dict[int, Dict]]:
    """Generate a hidden ground truth tier for each player.

    Philosophy:
    - Create a *latent skill* score that mixes core mechanics, decision/awareness, role-fit, and consistency.
    - Add mild stochasticity (so tiers are not perfectly reducible to an obvious single attribute average).
    - Assign tiers by quantiles according to cfg.tier_distribution.

    Returns:
        (truth_rows, truth_map)
    """

    rng = random.Random(seed)

    scored: List[Tuple[float, PlayerProfile, Dict[str, float]]] = []
    for p in players:
        core = _core_skill(p)
        role_fit = _role_fit(p)
        cons_factor = _consistency_factor(p)

        latent = (0.60 * core + 0.25 * role_fit + 0.15 * (p.objective_focus + p.teamplay) / 2.0)
        latent *= cons_factor

        # Add mild noise inversely proportional to consistency
        noise = rng.uniform(-6.0, 6.0) * (1.0 - p.consistency / 100.0)
        latent = max(1.0, min(100.0, latent + noise))

        scored.append((latent, p, {"CoreSkill": core, "RoleFit": role_fit, "ConsistencyFactor": cons_factor}))

    scored.sort(key=lambda x: x[0])

    # Convert distribution to cut indices
    dist = cfg.tier_distribution
    if not math.isclose(sum(dist), 1.0, abs_tol=1e-6):
        raise ValueError("tier_distribution must sum to 1.0")

    n = len(scored)
    cut_bronze = int(dist[0] * n)
    cut_silver = cut_bronze + int(dist[1] * n)
    cut_gold = cut_silver + int(dist[2] * n)
    # diamond takes the remainder

    truth_rows: List[Dict] = []
    truth_map: Dict[int, Dict] = {}

    for idx, (latent, p, parts) in enumerate(scored):
        if idx < cut_bronze:
            tier = "Bronze"
        elif idx < cut_silver:
            tier = "Silver"
        elif idx < cut_gold:
            tier = "Gold"
        else:
            tier = "Diamond"

        row = {
            "PlayerName": p.player_name,
            "PlayerID": p.player_id,
            "TrueTier": tier,
            "LatentSkill": round(latent, 3),
            "RoleFit": round(parts["RoleFit"], 3),
            "CoreSkill": round(parts["CoreSkill"], 3),
            "ConsistencyFactor": round(parts["ConsistencyFactor"], 3),
        }
        truth_rows.append(row)
        truth_map[p.player_id] = row

    # Return in PlayerID order for easier joining
    truth_rows.sort(key=lambda r: r["PlayerID"])

    return truth_rows, truth_map

def generate_ground_truth_attr_perf(
    players: List[PlayerProfile],
    student_rows: List[Dict],
    cfg: TournamentConfig,
    *,
    seed: int,
) -> Tuple[List[Dict], Dict[int, Dict]]:
    """
    Ground truth = attribute latent + aggregated simulated performance.

    - Attribute latent uses your existing _core_skill/_role_fit/_consistency_factor logic.
    - Performance score is computed from student_rows using min-max normalization.
    - Combined score is then tiered using cfg.tier_distribution.
    """

    rng = random.Random(seed)

    # --- Build lookup: PlayerID -> aggregated row ---
    perf_by_id: Dict[int, Dict] = {r["PlayerID"]: r for r in student_rows}

    # --- Min-max normalization helper (across all players) ---
    def minmax(key: str) -> Dict[int, float]:
        vals = [float(r.get(key, 0.0)) for r in student_rows]
        mn, mx = min(vals), max(vals)
        if mx - mn < 1e-9:
            return {r["PlayerID"]: 0.0 for r in student_rows}
        return {r["PlayerID"]: (float(r.get(key, 0.0)) - mn) / (mx - mn) for r in student_rows}

    # Choose performance features (you already compute most of these)
    n_win = minmax("WinRate")
    n_cap = minmax("CapturesPerMatch")
    n_obj = minmax("ObjectiveActionsPerMatch")
    n_ret = minmax("ReturnsPerMatch")
    n_int = minmax("InterceptionsPerMatch")
    n_def = minmax("DefenseStopsNearFlagPerMatch") if "DefenseStopsNearFlagPerMatch" in student_rows[0] else {r["PlayerID"]: 0.0 for r in student_rows}
    n_esc = minmax("TimeNearCarrierPerMatch") if "TimeNearCarrierPerMatch" in student_rows[0] else {r["PlayerID"]: 0.0 for r in student_rows}
    n_kdr = minmax("KDR")  # keep small weight so it doesn't dominate

    scored: List[Tuple[float, PlayerProfile, Dict[str, float]]] = []

    for p in players:
        core = _core_skill(p)
        role_fit = _role_fit(p)
        cons_factor = _consistency_factor(p)

        # Same attribute latent you already used
        attr_latent = (0.60 * core + 0.25 * role_fit + 0.15 * (p.objective_focus + p.teamplay) / 2.0)
        attr_latent *= cons_factor

        # Mild noise inversely proportional to consistency (keep your “not trivially reducible” property)
        noise = rng.uniform(-6.0, 6.0) * (1.0 - p.consistency / 100.0)
        attr_latent = max(1.0, min(100.0, attr_latent + noise))

        pid = p.player_id

        # Performance score in [0,1] (normalized across the whole cohort)
        perf_score_01 = (
            0.22 * n_win[pid] +
            0.22 * n_cap[pid] +
            0.14 * n_obj[pid] +
            0.10 * n_ret[pid] +
            0.10 * n_int[pid] +
            0.12 * n_def[pid] +
            0.06 * n_esc[pid] +
            0.04 * n_kdr[pid]
        )

        perf_score = 100.0 * perf_score_01  # scale to 0–100

        # Combined truth score (tunable weights)
        combined = 0.65 * attr_latent + 0.35 * perf_score

        scored.append(
            (combined, p, {
                "LatentSkill": attr_latent,
                "PerfScore": perf_score,
                "CombinedScore": combined,
                "CoreSkill": core,
                "RoleFit": role_fit,
                "ConsistencyFactor": cons_factor,
            })
        )

    scored.sort(key=lambda x: x[0])

    # Tier assignment using your existing distribution method
    dist = cfg.tier_distribution
    if not math.isclose(sum(dist), 1.0, abs_tol=1e-6):
        raise ValueError("tier_distribution must sum to 1.0")

    n = len(scored)
    cut_bronze = int(dist[0] * n)
    cut_silver = cut_bronze + int(dist[1] * n)
    cut_gold = cut_silver + int(dist[2] * n)

    truth_rows: List[Dict] = []
    truth_map: Dict[int, Dict] = {}

    for idx, (combined, p, parts) in enumerate(scored):
        if idx < cut_bronze:
            tier = "Bronze"
        elif idx < cut_silver:
            tier = "Silver"
        elif idx < cut_gold:
            tier = "Gold"
        else:
            tier = "Diamond"

        row = {
            "PlayerName": p.player_name,
            "PlayerID": p.player_id,
            "TrueTier": tier,
            "LatentSkill": round(parts["LatentSkill"], 3),
            "PerfScore": round(parts["PerfScore"], 3),
            "CombinedScore": round(parts["CombinedScore"], 3),
            "RoleFit": round(parts["RoleFit"], 3),
            "CoreSkill": round(parts["CoreSkill"], 3),
            "ConsistencyFactor": round(parts["ConsistencyFactor"], 3),
        }
        truth_rows.append(row)
        truth_map[p.player_id] = row

    truth_rows.sort(key=lambda r: r["PlayerID"])
    return truth_rows, truth_map


def _core_skill(p: PlayerProfile) -> float:
    """Core competence proxy (0-100-ish)."""

    return (
        0.18 * p.aim
        + 0.16 * p.movement
        + 0.14 * p.positioning
        + 0.14 * p.awareness
        + 0.12 * p.decision_making
        + 0.08 * p.route_knowledge
        + 0.08 * p.adaptability
        + 0.10 * p.teamplay
    )


def _consistency_factor(p: PlayerProfile) -> float:
    """Multiplicative factor ~[0.90, 1.05]."""

    # High consistency nudges upward slightly; low consistency slightly downward.
    return 0.90 + 0.15 * (p.consistency / 100.0)


def _role_fit(p: PlayerProfile) -> float:
    """Role-fit score based on preferred role weighting."""

    if p.preferred_role == Role.RUNNER:
        return (
            0.28 * p.movement
            + 0.18 * p.route_knowledge
            + 0.16 * p.awareness
            + 0.14 * p.decision_making
            + 0.14 * p.objective_focus
            + 0.10 * p.adaptability
        )

    if p.preferred_role == Role.DEFENDER:
        return (
            0.24 * p.positioning
            + 0.18 * p.awareness
            + 0.16 * p.recovery_discipline
            + 0.14 * p.aim
            + 0.14 * p.consistency
            + 0.14 * p.decision_making
        )

    if p.preferred_role == Role.SUPPORT:
        return (
            0.24 * p.teamplay
            + 0.18 * p.awareness
            + 0.16 * p.positioning
            + 0.14 * p.aim
            + 0.14 * p.decision_making
            + 0.14 * p.objective_focus
        )

    # MIDFIELD
    return (
        0.22 * p.aim
        + 0.18 * p.movement
        + 0.18 * p.awareness
        + 0.14 * p.positioning
        + 0.14 * p.adaptability
        + 0.14 * p.decision_making
    )


# ============================================================
# Aggregation
# ============================================================

@dataclass
class PlayerAggregate:
    player_name: str
    player_id: int
    preferred_role: str

    matches: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0

    kills: int = 0
    deaths: int = 0
    duels_won: int = 0
    duels_lost: int = 0
    flag_grabs: int = 0
    captures: int = 0
    returns: int = 0
    interceptions: int = 0
    defense_stops: int = 0
    overextensions: int = 0
    objective_actions: int = 0
    time_near_carrier: int = 0
    kills_while_carrier_alive: int = 0
    defense_stops_near_flag: int = 0
    returns_under_pressure: int = 0
    flag_room_presence_under_threat: int = 0
    kills_near_carrier: int = 0

    def to_export_row(self) -> dict:
        matches = max(1, self.matches)
        return {
            "PlayerName": self.player_name,
            "PlayerID": self.player_id,
            "PreferredRole": self.preferred_role,
            "Matches": self.matches,
            "Wins": self.wins,
            "Losses": self.losses,
            "Draws": self.draws,
            "Kills": self.kills,
            "Deaths": self.deaths,
            "DuelsWon": self.duels_won,
            "DuelsLost": self.duels_lost,
            "FlagGrabs": self.flag_grabs,
            "Captures": self.captures,
            "Returns": self.returns,
            "Interceptions": self.interceptions,
            "DefenseStops": self.defense_stops,
            "Overextensions": self.overextensions,
            "ObjectiveActions": self.objective_actions,
            "TimeNearCarrier": self.time_near_carrier,
            "KillsWhileCarrierAlive": self.kills_while_carrier_alive,
            "DefenseStopsNearFlag": self.defense_stops_near_flag,
            "ReturnsUnderPressure": self.returns_under_pressure,
            "FlagRoomPresenceUnderThreat": self.flag_room_presence_under_threat,
            "KillsNearCarrier": self.kills_near_carrier,
            "KDR": self.kills / max(1, self.deaths),
            "KillsPerMatch": self.kills / matches,
            "DeathsPerMatch": self.deaths / matches,
            "CapturesPerMatch": self.captures / matches,
            "GrabsPerMatch": self.flag_grabs / matches,
            "ReturnsPerMatch": self.returns / matches,
            "InterceptionsPerMatch": self.interceptions / matches,
            "ObjectiveActionsPerMatch": self.objective_actions / matches,
            "WinRate": self.wins / matches,
            "TimeNearCarrierPerMatch": self.time_near_carrier / matches,
            "KillsWhileCarrierAlivePerMatch": self.kills_while_carrier_alive / matches,
            "DefenseStopsNearFlagPerMatch": self.defense_stops_near_flag / matches,
            "ReturnsUnderPressurePerMatch": self.returns_under_pressure / matches,
            "FlagRoomPresenceUnderThreatPerMatch": self.flag_room_presence_under_threat / matches,
            "KillsNearCarrierPerMatch": self.kills_near_carrier / matches,
        }


def _init_aggregates(players: Iterable[PlayerProfile]) -> dict[int, PlayerAggregate]:
    agg: dict[int, PlayerAggregate] = {}
    for p in players:
        agg[p.player_id] = PlayerAggregate(
            player_name=p.player_name,
            player_id=p.player_id,
            preferred_role=p.preferred_role.value,
        )
    return agg


def _accumulate_match_result(
    agg: dict[int, PlayerAggregate],
    player_rows: list[dict],
    red_score: int,
    blue_score: int,
) -> None:
    if red_score > blue_score:
        red_outcome, blue_outcome = "win", "loss"
    elif blue_score > red_score:
        red_outcome, blue_outcome = "loss", "win"
    else:
        red_outcome = blue_outcome = "draw"

    for row in player_rows:
        pid = row["PlayerID"]
        team = row["Team"]
        a = agg[pid]

        a.matches += 1

        if team == Team.RED.value:
            outcome = red_outcome
        else:
            outcome = blue_outcome

        if outcome == "win":
            a.wins += 1
        elif outcome == "loss":
            a.losses += 1
        else:
            a.draws += 1

        a.kills += int(row.get("Kills", 0))
        a.deaths += int(row.get("Deaths", 0))
        a.duels_won += int(row.get("DuelsWon", 0))
        a.duels_lost += int(row.get("DuelsLost", 0))
        a.flag_grabs += int(row.get("FlagGrabs", 0))
        a.captures += int(row.get("Captures", 0))
        a.returns += int(row.get("Returns", 0))
        a.interceptions += int(row.get("Interceptions", 0))
        a.defense_stops += int(row.get("DefenseStops", 0))
        a.overextensions += int(row.get("Overextensions", 0))
        a.objective_actions += int(row.get("ObjectiveActions", 0))
        a.time_near_carrier += int(row.get("TimeNearCarrier", 0))
        a.kills_while_carrier_alive += int(row.get("KillsWhileCarrierAlive", 0))
        a.defense_stops_near_flag += int(row.get("DefenseStopsNearFlag", 0))
        a.returns_under_pressure += int(row.get("ReturnsUnderPressure", 0))
        a.flag_room_presence_under_threat += int(row.get("FlagRoomPresenceUnderThreat", 0))
        a.kills_near_carrier += int(row.get("KillsNearCarrier", 0))


def _finalize_aggregates(agg: dict[int, PlayerAggregate]) -> list[dict]:
    out = [a.to_export_row() for a in agg.values()]
    out.sort(key=lambda r: (r["WinRate"], r["CapturesPerMatch"], r["KDR"]), reverse=True)
    return out


# ============================================================
# Minimal CLI demo
# ============================================================

if __name__ == "__main__":
    

    # Demo with 100 synthetic players.
    # In your project, you'll load these from CSV/JSON.
    
     # Total Number of Players Generated - Might want to move this, but for now lets keep it here.
    num_player: int = 100

    # Configure the Tournament variables - Lets keep it with the default values and role-balanced.
    # Overrides possible for seed, n_matches... (see above)
    tcfg = TournamentConfig()

    # NOTE: behavior_tendencies in the engine uses an Enum.
    # If your PlayerProfile currently expects BehaviorTendency values, pass those enums instead.
    tendency_values = [
        BehaviorTendency.OVEREXTENDS_OFTEN,
        BehaviorTendency.TOO_PASSIVE,
        BehaviorTendency.SELFISH_FRAGGER,
        BehaviorTendency.DISCIPLINED_ANCHOR,
        BehaviorTendency.PANIC_UNDER_PRESSURE,
        BehaviorTendency.STRONG_UNDER_OBJECTIVE_PRESSURE,
        BehaviorTendency.INCONSISTENT_HIGH_CEILING,
    ]

    # Lets use the tournament config seed to keep everything deterministic.
    _r = random.Random(tcfg.base_seed)
    all_players: List[PlayerProfile] = []
    for i in range(num_player):
        role = [Role.RUNNER, Role.SUPPORT, Role.DEFENDER, Role.MIDFIELD][i % 4]
        all_players.append(
            PlayerProfile(
                player_name=f"P{i+1}",
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

    # Run the Tournaments here.
    student_rows, truth_rows = run_tournament(all_players, tournament_cfg=tcfg, include_ground_truth=True)

    assert truth_rows is not None

    write_student_and_truth_csv(
        student_rows,
        truth_rows,
        student_csv_path="students_dataset.csv",
        truth_csv_path="ground_truth_hidden.csv",
    )

    print("Wrote students_dataset.csv and ground_truth_hidden.csv")

    # --- quick sanity check: mean CombinedScore by tier ---
    tier_order = ["Bronze", "Silver", "Gold", "Diamond"]
    means = {
        t: sum(r["CombinedScore"] for r in truth_rows if r["TrueTier"] == t) / max(1, sum(1 for r in truth_rows if r["TrueTier"] == t))
        for t in tier_order
    }
    print("Mean CombinedScore by tier:", " | ".join(f"{t}={means[t]:.2f}" for t in tier_order))

    counts = {t: sum(1 for r in truth_rows if r["TrueTier"] == t) for t in tier_order}
    print("Tier counts:", counts)

    