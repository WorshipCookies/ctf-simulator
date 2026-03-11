from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math
import random
from BehaviorTendency import BehaviorTendency


# ============================================================
# Core enums
# ============================================================

class Role(str, Enum):
    RUNNER = "runner"
    SUPPORT = "support"
    DEFENDER = "defender"
    MIDFIELD = "midfield"

class Team(str, Enum):
    RED = "red"
    BLUE = "blue"


class ZoneType(str, Enum):
    BASE = "base"
    ENTRANCE = "entrance"
    CORRIDOR = "corridor"
    MID = "mid"
    ELEVATED = "elevated"


class FlagState(str, Enum):
    HOME = "home"
    TAKEN = "taken"
    DROPPED = "dropped"


class PlayerState(str, Enum):
    ALIVE = "alive"
    RESPAWNING = "respawning"


# ============================================================
# Player data model
# ============================================================

@dataclass
class PlayerProfile:
    player_name: str
    player_id: int
    aim: int
    movement: int
    positioning: int
    awareness: int
    teamplay: int
    decision_making: int
    consistency: int
    aggression: int
    objective_focus: int
    route_knowledge: int
    recovery_discipline: int
    adaptability: int
    preferred_role: Role
    behavior_tendencies: List[BehaviorTendency]

    def validate(self) -> None:
        numeric_fields = [
            "aim",
            "movement",
            "positioning",
            "awareness",
            "teamplay",
            "decision_making",
            "consistency",
            "aggression",
            "objective_focus",
            "route_knowledge",
            "recovery_discipline",
            "adaptability",
        ]
        for field_name in numeric_fields:
            value = getattr(self, field_name)
            if not 1 <= value <= 100:
                raise ValueError(f"{field_name} must be between 1 and 100, got {value}")


@dataclass
class PlayerRuntime:
    
    @property
    def player_id(self) -> int:
        return self.profile.player_id

    profile: PlayerProfile
    team: Team
    current_zone: str
    hp: int = 100
    state: PlayerState = PlayerState.ALIVE
    respawn_timer: int = 0
    carrying_flag_of: Optional[Team] = None

    # dynamic state
    current_role: Role = field(init=False)
    target_zone: Optional[str] = None
    pressure: float = 0.0

    # telemetry accumulators
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    flag_grabs: int = 0
    captures: int = 0
    returns: int = 0
    interceptions: int = 0
    escort_events: int = 0
    support_value: float = 0.0
    defense_stops: int = 0
    overextensions: int = 0
    duels_won: int = 0
    duels_lost: int = 0
    objective_actions: int = 0
    time_near_carrier: int = 0
    kills_while_carrier_alive: int = 0
    defense_stops_near_flag: int = 0
    returns_under_pressure: int = 0
    flag_room_presence_under_threat: int = 0
    flag_room_presence: int = 0
    kills_near_carrier: int = 0
    zone_time: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.current_role = self.profile.preferred_role

    @property
    def alive(self) -> bool:
        return self.state == PlayerState.ALIVE


# ============================================================
# Map model
# ============================================================

@dataclass
class Zone:
    zone_id: str
    zone_type: ZoneType
    team_owner: Optional[Team] = None
    elevation: int = 0
    cover: float = 0.0
    route_value: float = 0.0
    connected_to: List[str] = field(default_factory=list)


class CTFMap:
    """
    Symmetrical map with:
    - slightly elevated bases
    - 4 entrances into each base/flag area
    - 3 intertwining corridors connecting both halves
    """

    def __init__(self) -> None:
        self.zones: Dict[str, Zone] = {}
        self._build_default_map()

    def _add_zone(
        self,
        zone_id: str,
        zone_type: ZoneType,
        team_owner: Optional[Team] = None,
        elevation: int = 0,
        cover: float = 0.0,
        route_value: float = 0.0,
    ) -> None:
        self.zones[zone_id] = Zone(
            zone_id=zone_id,
            zone_type=zone_type,
            team_owner=team_owner,
            elevation=elevation,
            cover=cover,
            route_value=route_value,
        )

    def _connect(self, a: str, b: str) -> None:
        if b not in self.zones[a].connected_to:
            self.zones[a].connected_to.append(b)
        if a not in self.zones[b].connected_to:
            self.zones[b].connected_to.append(a)

    def _build_default_map(self) -> None:
        # Red base cluster
        self._add_zone("red_flag", ZoneType.BASE, team_owner=Team.RED, elevation=1, cover=0.45, route_value=1.0)
        for idx in range(1, 5):
            self._add_zone(
                f"red_entrance_{idx}",
                ZoneType.ENTRANCE,
                team_owner=Team.RED,
                elevation=1 if idx in (1, 2) else 0,
                cover=0.25,
                route_value=0.7,
            )

        # Blue base cluster
        self._add_zone("blue_flag", ZoneType.BASE, team_owner=Team.BLUE, elevation=1, cover=0.45, route_value=1.0)
        for idx in range(1, 5):
            self._add_zone(
                f"blue_entrance_{idx}",
                ZoneType.ENTRANCE,
                team_owner=Team.BLUE,
                elevation=1 if idx in (1, 2) else 0,
                cover=0.25,
                route_value=0.7,
            )

        # Intertwining corridors and mid control zones
        corridor_specs = [
            ("top", 1),
            ("mid", 0),
            ("bot", -1),
        ]
        for name, elevation in corridor_specs:
            self._add_zone(f"red_{name}_lane", ZoneType.CORRIDOR, team_owner=None, elevation=elevation, cover=0.20, route_value=0.8)
            self._add_zone(f"center_{name}", ZoneType.MID, team_owner=None, elevation=elevation, cover=0.15, route_value=1.0)
            self._add_zone(f"blue_{name}_lane", ZoneType.CORRIDOR, team_owner=None, elevation=elevation, cover=0.20, route_value=0.8)

        # Extra intertwining cross-links to support route planning
        self._add_zone("center_high", ZoneType.ELEVATED, team_owner=None, elevation=2, cover=0.10, route_value=1.1)
        self._add_zone("center_low", ZoneType.CORRIDOR, team_owner=None, elevation=-1, cover=0.30, route_value=0.9)

        # Base to entrances
        for idx in range(1, 5):
            self._connect("red_flag", f"red_entrance_{idx}")
            self._connect("blue_flag", f"blue_entrance_{idx}")

        # Entrances feed lanes in a mirrored but slightly varied way
        self._connect("red_entrance_1", "red_top_lane")
        self._connect("red_entrance_2", "red_mid_lane")
        self._connect("red_entrance_3", "red_bot_lane")
        self._connect("red_entrance_4", "red_mid_lane")

        self._connect("blue_entrance_1", "blue_top_lane")
        self._connect("blue_entrance_2", "blue_mid_lane")
        self._connect("blue_entrance_3", "blue_bot_lane")
        self._connect("blue_entrance_4", "blue_mid_lane")

        # Lanes to center
        self._connect("red_top_lane", "center_top")
        self._connect("red_mid_lane", "center_mid")
        self._connect("red_bot_lane", "center_bot")

        self._connect("blue_top_lane", "center_top")
        self._connect("blue_mid_lane", "center_mid")
        self._connect("blue_bot_lane", "center_bot")

        # Intertwining links
        self._connect("red_top_lane", "red_mid_lane")
        self._connect("red_mid_lane", "red_bot_lane")
        self._connect("blue_top_lane", "blue_mid_lane")
        self._connect("blue_mid_lane", "blue_bot_lane")

        self._connect("center_top", "center_mid")
        self._connect("center_mid", "center_bot")
        self._connect("center_top", "center_high")
        self._connect("center_mid", "center_high")
        self._connect("center_mid", "center_low")
        self._connect("center_bot", "center_low")

        # Cross connections to produce intertwined routing
        self._connect("red_top_lane", "center_high")
        self._connect("red_bot_lane", "center_low")
        self._connect("blue_top_lane", "center_high")
        self._connect("blue_bot_lane", "center_low")

    def neighbors(self, zone_id: str) -> List[str]:
        return self.zones[zone_id].connected_to

    def shortest_path(self, start: str, goal: str) -> List[str]:
        if start == goal:
            return [start]
        queue: List[Tuple[str, List[str]]] = [(start, [start])]
        visited = {start}
        while queue:
            node, path = queue.pop(0)
            for nxt in self.zones[node].connected_to:
                if nxt == goal:
                    return path + [nxt]
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [nxt]))
        return [start]


# ============================================================
# Match state
# ============================================================

@dataclass
class Flag:
    owner_team: Team
    home_zone: str
    state: FlagState = FlagState.HOME
    carrier_player_id: Optional[int] = None
    dropped_zone: Optional[str] = None


@dataclass
class MatchConfig:
    tick_limit: int = 500
    respawn_ticks: int = 8
    fight_radius_same_zone: bool = True
    base_capture_score: int = 1
    flag_return_touch: bool = True
    movement_base_chance: float = 0.65
    fight_engage_base_chance: float = 0.55
    randomness_seed: int = 42


@dataclass
class MatchResult:
    red_score: int
    blue_score: int
    ticks_played: int
    player_telemetry: List[Dict]


# ============================================================
# Engine
# ============================================================

class CTFMatchSimulation:
    def __init__(self, players: List[PlayerProfile], config: Optional[MatchConfig] = None):
        if len(players) != 8:
            raise ValueError("This engine currently expects exactly 8 players for one 4v4 match.")

        self.config = config or MatchConfig()
        self.rng = random.Random(self.config.randomness_seed)
        self.map = CTFMap()

        self.players: Dict[int, PlayerRuntime] = {}
        self.red_team: List[int] = []
        self.blue_team: List[int] = []

        for idx, p in enumerate(players):
            p.validate()
            team = Team.RED if idx < 4 else Team.BLUE
            spawn = "red_flag" if team == Team.RED else "blue_flag"
            runtime = PlayerRuntime(profile=p, team=team, current_zone=spawn)
            self.players[p.player_id] = runtime
            if team == Team.RED:
                self.red_team.append(p.player_id)
            else:
                self.blue_team.append(p.player_id)

        self.flags = {
            Team.RED: Flag(owner_team=Team.RED, home_zone="red_flag"),
            Team.BLUE: Flag(owner_team=Team.BLUE, home_zone="blue_flag"),
        }

        self.red_score = 0
        self.blue_score = 0
        self.tick = 0

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    def run(self) -> MatchResult:
        for current_tick in range(self.config.tick_limit):
            self.tick = current_tick
            self._tick_respawns()
            self._update_roles()
            self._choose_targets()
            self._movement_phase()
            self._combat_phase()
            self._objective_phase()
            self._log_zone_time()

        return MatchResult(
            red_score=self.red_score,
            blue_score=self.blue_score,
            ticks_played=self.config.tick_limit,
            player_telemetry=self._export_telemetry(),
        )

    # --------------------------------------------------------
    # Phase logic
    # --------------------------------------------------------

    def _tick_respawns(self) -> None:
        for player in self.players.values():
            if player.state == PlayerState.RESPAWNING:
                player.respawn_timer -= 1
                if player.respawn_timer <= 0:
                    player.state = PlayerState.ALIVE
                    player.hp = 100
                    player.current_zone = "red_flag" if player.team == Team.RED else "blue_flag"
                    player.target_zone = None
                    player.pressure = 0.0

    def _update_roles(self) -> None:
        for player in self.players.values():
            if not player.alive:
                continue

            own_flag = self.flags[player.team]
            enemy_team = Team.BLUE if player.team == Team.RED else Team.RED
            enemy_flag = self.flags[enemy_team]

            # Dynamic role shifting according to match state
            if player.carrying_flag_of is not None:
                player.current_role = Role.RUNNER
            elif own_flag.state == FlagState.TAKEN:
                if player.profile.recovery_discipline + player.profile.awareness > 120:
                    player.current_role = Role.MIDFIELD
            elif enemy_flag.state == FlagState.HOME and player.profile.preferred_role == Role.RUNNER:
                player.current_role = Role.RUNNER
            elif player.profile.preferred_role == Role.DEFENDER and player.profile.positioning + player.profile.consistency > 120:
                player.current_role = Role.DEFENDER
            else:
                player.current_role = player.profile.preferred_role

    def _choose_targets(self) -> None:
        for player in self.players.values():
            if not player.alive:
                continue

            enemy_team = Team.BLUE if player.team == Team.RED else Team.RED
            own_flag = self.flags[player.team]
            enemy_flag = self.flags[enemy_team]

            if player.carrying_flag_of is not None:
                player.target_zone = self.flags[player.team].home_zone
                continue

            if player.current_role == Role.DEFENDER:
                player.target_zone = self._pick_defensive_zone(player)
            elif player.current_role == Role.MIDFIELD:
                if own_flag.state == FlagState.TAKEN:
                    player.target_zone = self._predict_carrier_intercept_zone(player.team)
                else:
                    player.target_zone = self._pick_midfield_zone(player)
            elif player.current_role == Role.SUPPORT:
                carrier = self._friendly_flag_carrier(player.team)
                if carrier is not None:
                    player.target_zone = self.players[carrier].current_zone
                else:
                    player.target_zone = self._pick_attack_staging_zone(player)
            elif player.current_role == Role.RUNNER:
                if enemy_flag.state == FlagState.HOME:
                    player.target_zone = enemy_flag.home_zone
                elif enemy_flag.state == FlagState.DROPPED and enemy_flag.dropped_zone is not None:
                    player.target_zone = enemy_flag.dropped_zone
                else:
                    player.target_zone = self._pick_attack_staging_zone(player)
            else:
                player.target_zone = self._pick_midfield_zone(player)

    def _movement_phase(self) -> None:
        for player in self.players.values():
            if not player.alive or not player.target_zone:
                continue
            if player.current_zone == player.target_zone:
                continue

            path = self.map.shortest_path(player.current_zone, player.target_zone)
            if len(path) < 2:
                continue

            move_bias = self._movement_score(player)
            move_prob = min(0.95, self.config.movement_base_chance + (move_bias - 50) / 200.0)

            if self.rng.random() < move_prob:
                next_zone = path[1]
                player.current_zone = next_zone

                # Behavior-based overextension logging
                if self._is_overextended(player):
                    player.overextensions += 1

    def _combat_phase(self) -> None:
        zone_to_players: Dict[str, List[PlayerRuntime]] = {}
        for player in self.players.values():
            if player.alive:
                zone_to_players.setdefault(player.current_zone, []).append(player)

        for zone_id, present in zone_to_players.items():
            red_present = [p for p in present if p.team == Team.RED]
            blue_present = [p for p in present if p.team == Team.BLUE]
            if not red_present or not blue_present:
                continue

            # Repeated small skirmish resolution per contested zone
            num_duels = min(len(red_present), len(blue_present))
            for _ in range(num_duels):
                if not red_present or not blue_present:
                    break
                red_player = self.rng.choice(red_present)
                blue_player = self.rng.choice(blue_present)
                winner, loser = self._resolve_duel(red_player, blue_player, zone_id)
                self._apply_frag(winner, loser)
                if loser.team == Team.RED:
                    red_present = [p for p in red_present if p.profile.player_id != loser.profile.player_id]
                else:
                    blue_present = [p for p in blue_present if p.profile.player_id != loser.profile.player_id]

    def _objective_phase(self) -> None:
        for player in self.players.values():
            if not player.alive:
                continue

            enemy_team = Team.BLUE if player.team == Team.RED else Team.RED
            enemy_flag = self.flags[enemy_team]
            own_flag = self.flags[player.team]

            # Grab enemy flag
            if (
                player.current_zone == enemy_flag.home_zone
                and enemy_flag.state == FlagState.HOME
                and player.carrying_flag_of is None
            ):
                grab_prob = self._flag_grab_score(player) / 100.0
                if self.rng.random() < grab_prob:
                    enemy_flag.state = FlagState.TAKEN
                    enemy_flag.carrier_player_id = player.profile.player_id
                    enemy_flag.dropped_zone = None
                    player.carrying_flag_of = enemy_team
                    player.flag_grabs += 1
                    player.objective_actions += 1

            # Return dropped own flag
            if own_flag.state == FlagState.DROPPED and own_flag.dropped_zone == player.current_zone:
                return_prob = self._flag_return_score(player) / 100.0
                if self.rng.random() < return_prob:
                    own_flag.state = FlagState.HOME
                    own_flag.carrier_player_id = None
                    own_flag.dropped_zone = None
                    player.returns += 1
                    # Increment “returns under pressure”
                    if self._zone_is_contested(player.current_zone) or player.pressure > 0.6:
                        player.returns_under_pressure += 1
                    player.objective_actions += 1

            # Capture flag
            if player.carrying_flag_of is not None:
                if player.current_zone == own_flag.home_zone and own_flag.state == FlagState.HOME:
                    if player.team == Team.RED:
                        self.red_score += self.config.base_capture_score
                    else:
                        self.blue_score += self.config.base_capture_score

                    captured_team = player.carrying_flag_of
                    captured_flag = self.flags[captured_team]
                    captured_flag.state = FlagState.HOME
                    captured_flag.carrier_player_id = None
                    captured_flag.dropped_zone = None
                    player.carrying_flag_of = None
                    player.captures += 1
                    player.objective_actions += 1

    def _log_zone_time(self) -> None:
        for player in self.players.values():
            if not player.alive:
                continue
            player.zone_time[player.current_zone] = player.zone_time.get(player.current_zone, 0) + 1

            # Flag-room presence under threat (defense discipline signal)
            own_flag = self.flags[player.team]
            if own_flag.state != FlagState.HOME:
                # own-side zones = base or entrances prefixed by team color
                if player.team == Team.RED:
                    is_own_side = player.current_zone.startswith("red_")
                else:
                    is_own_side = player.current_zone.startswith("blue_")

                if is_own_side:
                    zt = self.map.zones[player.current_zone].zone_type
                    if zt in (ZoneType.BASE, ZoneType.ENTRANCE):
                        player.flag_room_presence_under_threat += 1
            
            # Check time player is near the flag carrier
            carrier_id = self._friendly_flag_carrier(player.team)
            if carrier_id is not None and player.profile.player_id != carrier_id:
                carrier_zone = self.players[carrier_id].current_zone
                if player.current_zone == carrier_zone or player.current_zone in self.map.neighbors(carrier_zone):
                    player.time_near_carrier += 1

    def _zone_is_contested(self, zone_id: str) -> bool:
        reds = 0
        blues = 0
        for p in self.players.values():
            if not p.alive:
                continue
            if p.current_zone != zone_id:
                continue
            if p.team == Team.RED:
                reds += 1
            else:
                blues += 1
        return reds > 0 and blues > 0

    # --------------------------------------------------------
    # Duel and scoring logic
    # --------------------------------------------------------

    def _resolve_duel(self, a: PlayerRuntime, b: PlayerRuntime, zone_id: str) -> Tuple[PlayerRuntime, PlayerRuntime]:
        zone = self.map.zones[zone_id]

        a_score = self._combat_score(a, zone)
        b_score = self._combat_score(b, zone)

        total = max(1e-6, a_score + b_score)
        a_win_prob = a_score / total

        if self.rng.random() < a_win_prob:
            return a, b
        return b, a

    def _combat_score(self, player: PlayerRuntime, zone: Zone) -> float:
        p = player.profile

        base = (
            0.28 * p.aim
            + 0.16 * p.movement
            + 0.14 * p.positioning
            + 0.12 * p.awareness
            + 0.10 * p.decision_making
            + 0.08 * p.consistency
            + 0.05 * p.adaptability
            + 0.07 * p.aggression
        )

        # Zone-specific bonuses
        if zone.elevation > 0:
            base += 0.10 * p.positioning + 0.05 * p.awareness
        if zone.zone_type == ZoneType.BASE and player.current_role == Role.DEFENDER:
            base += 0.16 * p.positioning + 0.10 * p.recovery_discipline
        if zone.zone_type in (ZoneType.MID, ZoneType.CORRIDOR) and player.current_role == Role.MIDFIELD:
            base += 0.12 * p.movement + 0.10 * p.adaptability

        # Behavior modifiers
        tendencies = set(player.profile.behavior_tendencies)
        if BehaviorTendency.PANIC_UNDER_PRESSURE in tendencies and player.pressure > 0.6:
            base *= 0.86
        if BehaviorTendency.STRONG_UNDER_OBJECTIVE_PRESSURE in tendencies and self._objective_hot_state(player):
            base *= 1.10
        if BehaviorTendency.INCONSISTENT_HIGH_CEILING in tendencies:
            base *= self.rng.uniform(0.80, 1.22)

        # Mild noise scaled by consistency
        noise_strength = max(0.02, (101 - p.consistency) / 220.0)
        base *= self.rng.uniform(1.0 - noise_strength, 1.0 + noise_strength)

        # Cover and route advantage
        base *= 1.0 + zone.cover * 0.10
        return max(1.0, base)

    def _apply_frag(self, winner: PlayerRuntime, loser: PlayerRuntime) -> None:
        winner.kills += 1
        
        friendly_carrier = self._friendly_flag_carrier(winner.team)

        # Increment “kills while flag carrier is alive”
        if friendly_carrier is not None:
            winner.kills_while_carrier_alive += 1

        # Tracks kills that happens near the carrier zone and neighboring zones (if not the flag carrier)
        if friendly_carrier is not None and friendly_carrier != winner.profile.player_id:
            carrier_zone = self.players[friendly_carrier].current_zone
            if winner.current_zone == carrier_zone or winner.current_zone in self.map.neighbors(carrier_zone):
                winner.kills_near_carrier += 1

        winner.duels_won += 1
        loser.deaths += 1
        loser.duels_lost += 1

        # Special defense/interception logging
        if loser.carrying_flag_of is not None:
            winner.interceptions += 1
            winner.objective_actions += 1
            dropped_flag_team = loser.carrying_flag_of
            dropped_flag = self.flags[dropped_flag_team]
            dropped_flag.state = FlagState.DROPPED
            dropped_flag.carrier_player_id = None
            dropped_flag.dropped_zone = loser.current_zone
            loser.carrying_flag_of = None

        if winner.current_role == Role.DEFENDER:
            winner.defense_stops += 1
            # Near-flag defense stop: base or entrance on your side
            if (winner.team == Team.RED and winner.current_zone.startswith("red_")) or \
               (winner.team == Team.BLUE and winner.current_zone.startswith("blue_")):
                if self.map.zones[winner.current_zone].zone_type in (ZoneType.BASE, ZoneType.ENTRANCE):
                    winner.defense_stops_near_flag += 1

        loser.state = PlayerState.RESPAWNING
        loser.respawn_timer = self.config.respawn_ticks
        loser.hp = 0
        loser.target_zone = None
        loser.pressure = 1.0

    # --------------------------------------------------------
    # Role-sensitive targeting
    # --------------------------------------------------------

    def _pick_defensive_zone(self, player: PlayerRuntime) -> str:
        if player.team == Team.RED:
            options = ["red_flag", "red_entrance_1", "red_entrance_2", "red_entrance_3", "red_entrance_4"]
        else:
            options = ["blue_flag", "blue_entrance_1", "blue_entrance_2", "blue_entrance_3", "blue_entrance_4"]
        return self.rng.choice(options)

    def _pick_midfield_zone(self, player: PlayerRuntime) -> str:
        weights = {
            "center_top": 1.0,
            "center_mid": 1.3,
            "center_bot": 1.0,
            "center_high": 0.9 + player.profile.positioning / 200.0,
            "center_low": 0.9,
        }
        return self._weighted_choice(weights)

    def _pick_attack_staging_zone(self, player: PlayerRuntime) -> str:
        if player.team == Team.RED:
            weights = {
                "blue_top_lane": 0.9 + player.profile.route_knowledge / 200.0,
                "blue_mid_lane": 1.1,
                "blue_bot_lane": 0.9 + player.profile.movement / 250.0,
            }
        else:
            weights = {
                "red_top_lane": 0.9 + player.profile.route_knowledge / 200.0,
                "red_mid_lane": 1.1,
                "red_bot_lane": 0.9 + player.profile.movement / 250.0,
            }
        return self._weighted_choice(weights)

    def _predict_carrier_intercept_zone(self, team: Team) -> str:
        enemy_carrier = self._enemy_flag_carrier(team)
        if enemy_carrier is not None:
            return self.players[enemy_carrier].current_zone
        return "center_mid"

    # --------------------------------------------------------
    # Heuristics and utilities
    # --------------------------------------------------------

    def _movement_score(self, player: PlayerRuntime) -> float:
        p = player.profile
        score = 0.40 * p.movement + 0.20 * p.route_knowledge + 0.20 * p.decision_making + 0.20 * p.consistency

        tendencies = set(p.behavior_tendencies)
        if BehaviorTendency.TOO_PASSIVE in tendencies:
            score *= 0.90
        if BehaviorTendency.OVEREXTENDS_OFTEN in tendencies:
            score *= 1.05
        return max(1.0, min(100.0, score))

    def _flag_grab_score(self, player: PlayerRuntime) -> float:
        p = player.profile
        score = (
            0.24 * p.movement
            + 0.16 * p.route_knowledge
            + 0.16 * p.objective_focus
            + 0.12 * p.awareness
            + 0.12 * p.decision_making
            + 0.10 * p.positioning
            + 0.10 * p.adaptability
        )
        if BehaviorTendency.STRONG_UNDER_OBJECTIVE_PRESSURE in p.behavior_tendencies:
            score *= 1.08
        return max(5.0, min(95.0, score))

    def _flag_return_score(self, player: PlayerRuntime) -> float:
        p = player.profile
        score = 0.30 * p.recovery_discipline + 0.24 * p.awareness + 0.20 * p.objective_focus + 0.14 * p.positioning + 0.12 * p.decision_making
        return max(5.0, min(95.0, score))

    def _friendly_flag_carrier(self, team: Team) -> Optional[int]:
        for player in self.players.values():
            if player.team == team and player.carrying_flag_of is not None:
                return player.profile.player_id
        return None

    def _enemy_flag_carrier(self, team: Team) -> Optional[int]:
        enemy_team = Team.BLUE if team == Team.RED else Team.RED
        return self._friendly_flag_carrier(enemy_team)

    def _objective_hot_state(self, player: PlayerRuntime) -> bool:
        enemy_team = Team.BLUE if player.team == Team.RED else Team.RED
        enemy_flag = self.flags[enemy_team]
        own_flag = self.flags[player.team]
        return (
            player.carrying_flag_of is not None
            or enemy_flag.state != FlagState.HOME
            or own_flag.state != FlagState.HOME
        )

    def _is_overextended(self, player: PlayerRuntime) -> bool:
        tendencies = set(player.profile.behavior_tendencies)
        if BehaviorTendency.OVEREXTENDS_OFTEN not in tendencies:
            return False

        enemy_base_prefix = "blue_" if player.team == Team.RED else "red_"
        in_enemy_side = player.current_zone.startswith(enemy_base_prefix) or player.current_zone in {"center_top", "center_mid", "center_bot", "center_high", "center_low"}

        ally_count = sum(
            1 for p in self.players.values()
            if p.alive and p.team == player.team and p.current_zone == player.current_zone
        )
        return in_enemy_side and ally_count <= 1

    def _weighted_choice(self, weights: Dict[str, float]) -> str:
        total = sum(weights.values())
        roll = self.rng.random() * total
        upto = 0.0
        for item, weight in weights.items():
            upto += weight
            if upto >= roll:
                return item
        return next(iter(weights.keys()))

    def _export_telemetry(self) -> List[Dict]:
        out: List[Dict] = []
        for player in self.players.values():
            out.append({
                "PlayerName": player.profile.player_name,
                "PlayerID": player.profile.player_id,
                "Team": player.team.value,
                "PreferredRole": player.profile.preferred_role.value,
                "Kills": player.kills,
                "Deaths": player.deaths,
                "DuelsWon": player.duels_won,
                "DuelsLost": player.duels_lost,
                "FlagGrabs": player.flag_grabs,
                "Captures": player.captures,
                "Returns": player.returns,
                "Interceptions": player.interceptions,
                "DefenseStops": player.defense_stops,
                "Overextensions": player.overextensions,
                "ObjectiveActions": player.objective_actions,
                "ZoneTime": dict(player.zone_time),
                "TimeNearCarrier": player.time_near_carrier,
                "KillsWhileCarrierAlive": player.kills_while_carrier_alive,
                "DefenseStopsNearFlag": player.defense_stops_near_flag,
                "ReturnsUnderPressure": player.returns_under_pressure,
                "FlagRoomPresenceUnderThreat": player.flag_room_presence_under_threat,
                "KillsNearCarrier": player.kills_near_carrier,
            })
        return out


# ============================================================
# Example usage
# ============================================================

if __name__ == "__main__":
    sample_players = [
        PlayerProfile(
            player_name=f"Player_{i+1}",
            player_id=i+1,
            aim=random.randint(40, 95),
            movement=random.randint(40, 95),
            positioning=random.randint(40, 95),
            awareness=random.randint(40, 95),
            teamplay=random.randint(40, 95),
            decision_making=random.randint(40, 95),
            consistency=random.randint(40, 95),
            aggression=random.randint(40, 95),
            objective_focus=random.randint(40, 95),
            route_knowledge=random.randint(40, 95),
            recovery_discipline=random.randint(40, 95),
            adaptability=random.randint(40, 95),
            preferred_role=[Role.RUNNER, Role.SUPPORT, Role.DEFENDER, Role.MIDFIELD][i % 4],
            behavior_tendencies=[random.choice(list(BehaviorTendency))],
        )
        for i in range(8)
    ]

    sim = CTFMatchSimulation(sample_players)
    result = sim.run()

    print("Final Score")
    print(f"RED {result.red_score} - {result.blue_score} BLUE")
    print("\nTelemetry sample:")
    for row in result.player_telemetry:
        print(row)
