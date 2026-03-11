# Arena Shooter CTF 4v4 - Simulator

This document explains the **internal mechanics of the simulator** used to generate the synthetic dataset.

Source files:
- ctf_match_simulation_engine.py
- tournament.py
- BehaviorTendency.py

---
# Architecture Overview
The system consists of two main parts:

### 1) Match Simulation Engine
Handles a single match between 8 agents.

### 2) Tournament Runner
Runs hundreds of matches and aggregates telemetry into a dataset.

---

# Match Simulation Loop

Each match runs for a fixed number of ticks.

Each tick performs:
1. Respawn handling
2. Dynamic role updates
3. Target selection
4. Movement
5. Combat resolution
6. Objective interactions
7. Telemetry logging

---

# Map Representation

The arena is represented as a **graph of zones**.

Zones include:

Base zones
- red_flag
- blue_flag

Entrances
- red_entrance_1..4
- blue_entrance_1..4

Lanes
- red_top_lane
- red_mid_lane
- red_bot_lane

Center zones
- center_top
- center_mid
- center_bot

Vertical routes
- center_high
- center_low

Movement uses shortest-path traversal between zones.

---

# Arena Layout

The arena is **symmetrical** to ensure fairness.

Each base:
- is slightly elevated
- contains the flag
- has **4 entrances**

Between bases there are **three main lanes**.

![alt text](/img/ArenaImage.png "Graph Arena Layout")

Legend
- `red_flag`  / `blue_flag` = flag rooms
- `E1–E4` = base entrances
- \_R or \_B = Red or Blue
- `top / mid / bot` = the three main corridors
- `center_high` = elevated central route
- `center_low` = lower alternative route

---

# Player Attributes

Each player has attributes in range 1–100.

Core attributes:
- aim
- movement
- positioning
- awareness
- teamplay
- decision_making
- consistency
- aggression
- objective_focus
- route_knowledge
- recovery_discipline
- adaptability

Players also have:
- preferred role
- behavioral tendencies

---

# Behavioral Tendencies

Examples:
- overextends often
- too passive
- selfish fragger
- disciplined anchor
- panic under pressure
- strong under objective pressure
- inconsistent high ceiling

These influence:
- movement probabilities
- combat effectiveness
- variance of outcomes

---

# Roles

Roles include:
- Runner
- Support
- Defender
- Midfield

Roles are dynamic and may change during a match.

Examples:

Runner → carrying flag  
Support → escort carrier  
Defender → guard base entrances  
Midfield → intercept enemy carrier

---

# Movement Model

Players move one zone per tick along a shortest path.

Movement probability depends on:
- movement
- route knowledge
- decision making
- consistency

Behavior tendencies modify movement aggressiveness.

---

# Combat Model

Combat occurs when opposing players occupy the same zone.

Duels are probabilistic.

Combat score includes:
- aim
- positioning
- movement
- awareness
- decision making
- aggression
- consistency

Environment modifiers:
- elevation
- cover
- zone type
- role bonuses

Consistency influences randomness.

---

# Objective System

Flag interactions include:

Grab
Return
Capture

Captures occur when:
enemy flag carried → returned to base  
AND  
own flag is present

---

# Telemetry Signals

Signals intentionally capture role impact.

Examples:

Escort metrics
- TimeNearCarrier

Anti-chaser support
- KillsNearCarrier

Offensive pressure
- KillsWhileCarrierAlive

Defense
- DefenseStopsNearFlag

Defensive discipline
- FlagRoomPresenceUnderThreat

High pressure plays
- ReturnsUnderPressure

---

# Tournament Aggregation

Many matches are simulated.

Player telemetry is aggregated:

- totals
- per-match averages
- derived ratios

Resulting rows form the `students_dataset.csv`.

---

# Ground Truth Generation

Hidden tiers combine:

1. Attribute-based latent skill
2. Simulated performance

Latent skill uses:

- core attributes
- role fit
- consistency modifier

Performance score uses normalized metrics including:

- win rate
- captures
- objective actions
- interceptions
- defensive metrics
- escort metrics

---

# Tier Assignment

CombinedScore = 0.65 * LatentSkill  + 0.35 * PerformanceScore

Players are ranked and split into:

Bronze → 40%  
Silver → 35%  
Gold → 20%  
Diamond → 5%

---

# Purpose of the Simulator

The simulator provides a **controlled synthetic dataset** for teaching:

- player modeling
- telemetry interpretation
- feature engineering
- ranking systems
- evaluation against hidden labels