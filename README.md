# Arena Shooter CTF 4v4 - Simulator

This document explains the **internal mechanics of the simulator** used to generate the synthetic dataset.

Source files:
- ctf_match_simulation_engine.py
- tournament.py
- BehaviorTendency.py

For the full mathematical specification of the simulator, see the [Mathematical Appendix](./apx/math.md).

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

- Grab
- Return
- Capture

Captures occur when:
```
enemy flag carried → returned to base  
AND  
own flag is present
```

---

# Telemetry Signals

Signals intentionally capture role impact.

Examples:

Escort metrics: `TimeNearCarrier`
Anti-chaser support: `KillsNearCarrier`
Offensive pressure: `KillsWhileCarrierAlive`
Defense: `DefenseStopsNearFlag`
Defensive discipline: `FlagRoomPresenceUnderThreat`
High pressure plays: `ReturnsUnderPressure`

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

CombinedScore = `0.65 * LatentSkill  + 0.35 * PerformanceScore`

Players are ranked and split into:

- Bronze → 40%  
- Silver → 35%  
- Gold → 20%  
- Diamond → 5%

---

# Purpose of the Simulator

The simulator provides a **controlled synthetic dataset** for teaching:

- player modeling
- telemetry interpretation
- feature engineering
- ranking systems
- evaluation against hidden labels

---

# Reference Map to Mathematical Appendix

This section links each high-level simulator concept in this document to its corresponding mathematical specification in the appendix.

Appendix location:

- [`/apx/math.md`](./apx/math.md)

---

## Quick Lookup Table

| Concept in this document | Mathematical appendix section |
|---|---|
| Match loop / tick order | [A.1 Simulation Time Model](./apx/math.md#a1-simulation-time-model) |
| Player attributes | [A.2 Player Attribute Vector](./apx/math.md#a2-player-attribute-vector) |
| Movement model | [A.3 Movement Model](./apx/math.md#a3-movement-model) |
| Movement probability | [A.3 Movement Model](./apx/math.md#a3-movement-model) |
| Overextension logic | [A.3 Movement Model](./apx/math.md#a3-movement-model) and [A.7 Behavioral Combat Modifiers](./apx/math.md#a7-behavioral-combat-modifiers) |
| Combat resolution | [A.4 Combat Resolution](./apx/math.md#a4-combat-resolution) |
| Combat score | [A.5 Combat Score](./apx/math.md#a5-combat-score) |
| Elevation / high ground | [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers) |
| High ground bonus | [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers) |
| Low ground interpretation | [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers) |
| Defender base bonus | [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers) |
| Midfield zone bonus | [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers) |
| Cover influence | [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers) |
| Behavioral tendencies in combat | [A.7 Behavioral Combat Modifiers](./apx/math.md#a7-behavioral-combat-modifiers) |
| Panic under pressure | [A.7 Behavioral Combat Modifiers](./apx/math.md#a7-behavioral-combat-modifiers) |
| Strong under objective pressure | [A.7 Behavioral Combat Modifiers](./apx/math.md#a7-behavioral-combat-modifiers) |
| Inconsistent high ceiling | [A.7 Behavioral Combat Modifiers](./apx/math.md#a7-behavioral-combat-modifiers) |
| Consistency and noise | [A.8 Consistency Noise](./apx/math.md#a8-consistency-noise) |
| Duel win probability | [A.9 Duel Outcome Probability](./apx/math.md#a9-duel-outcome-probability) |
| Flag grab probability | [A.10 Flag Grab Probability](./apx/math.md#a10-flag-grab-probability) |
| Flag return probability | [A.11 Flag Return Probability](./apx/math.md#a11-flag-return-probability) |
| Latent skill generation | [A.12 Latent Skill Model](./apx/math.md#a12-latent-skill-model) |
| Final hidden score / combined truth | [A.13 Final Skill Score](./apx/math.md#a13-final-skill-score) |
| Tier assignment | [A.13 Final Skill Score](./apx/math.md#a13-final-skill-score) |
| Design assumptions / interpretation | [A.14 Design Philosophy](./apx/math.md#a14-design-philosophy) |

---

## Concept-to-Appendix Crosswalk

### Architecture Overview
For the formal tick order and simulation sequencing, see:
- [A.1 Simulation Time Model](./apx/math.md#a1-simulation-time-model)

### Player Attributes
For the formal definition of the player attribute vector, see:
- [A.2 Player Attribute Vector](./apx/math.md#a2-player-attribute-vector)

### Behavioral Tendencies
For the mathematical effect of tendencies on movement, combat, and variance, see:
- [A.3 Movement Model](./apx/math.md#a3-movement-model)
- [A.7 Behavioral Combat Modifiers](./apx/math.md#a7-behavioral-combat-modifiers)
- [A.8 Consistency Noise](./apx/math.md#a8-consistency-noise)

### Movement Model
For the exact movement score equation and movement probability, see:
- [A.3 Movement Model](./apx/math.md#a3-movement-model)

### Combat Model
For duel resolution and combat score equations, see:
- [A.4 Combat Resolution](./apx/math.md#a4-combat-resolution)
- [A.5 Combat Score](./apx/math.md#a5-combat-score)
- [A.9 Duel Outcome Probability](./apx/math.md#a9-duel-outcome-probability)

### Environmental Modifiers
For elevation, high ground, defender bonuses, midfield bonuses, and cover, see:
- [A.6 Environmental Combat Modifiers](./apx/math.md#a6-environmental-combat-modifiers)

### Objective System
For flag grab and return probabilities, see:
- [A.10 Flag Grab Probability](./apx/math.md#a10-flag-grab-probability)
- [A.11 Flag Return Probability](./apx/math.md#a11-flag-return-probability)

### Ground Truth Generation
For the attribute-based latent score, performance-informed final score, and tier assignment, see:
- [A.12 Latent Skill Model](./apx/math.md#a12-latent-skill-model)
- [A.13 Final Skill Score](./apx/math.md#a13-final-skill-score)

### Interpretation / Design Philosophy
For the assumptions behind the simulator, especially the idea that skill is latent and telemetry is noisy, see:
- [A.14 Design Philosophy](./apx/math.md#a14-design-philosophy)

