This appendix documents the **formal mathematical specification** of the Arena Capture-the-Flag simulation used to generate the telemetry dataset.

The goal is to make the synthetic data generation process **transparent, reproducible, and explainable**.

All attributes are normalized to the range: [0, 100]


unless otherwise specified.

---

# A.1 Simulation Time Model

The simulation runs in **discrete ticks**.

Each tick executes the following ordered phases:

1. Respawn phase
2. Role update phase
3. Target selection
4. Movement
5. Combat
6. Objective interaction
7. Telemetry logging

Let: $t ∈ {1, 2, ..., T}$, be the tick index for a match of length $T$.

---
# A.2 Player Attribute Vector

Each player has a static attribute vector:

P = [  aim,  movement, positioning,  awareness,  teamplay,  decision_making,  consistency,  aggression,  objective_focus,  route_knowledge,  recovery_discipline,  adaptability  ]


All attributes are integer values in $[1,100]$.

These attributes influence:

- movement probability
- combat strength
- objective success probability
- behavioral noise

---

# A.3 Movement Model

Movement is **zone-based** rather than continuous.

Each player attempts to move one step along the shortest path to their target zone.

First we compute the **movement score**:

$movement_{score} = 0.40M + 0.20R + 0.20D + 0.20C$

Where:
- $M$ = movement
- $R$ = route_knowledge
- $D$ = decision_making
- $C$ = consistency

---
### Behavioral adjustments
Certain tendencies modify the movement score.

| Behavior          | Modifier |
| ----------------- | -------- |
| OVEREXTENDS_OFTEN | $× 1.05$  |
| TOO_PASSIVE       | $× 0.90$   |

---
### Movement probability

Movement score is converted to a movement probability:
$p_{move} = \min(0.95, 0.65 + \frac{movement_{score} - 50}{200})$

Interpretation:
- average players move with probability ≈ 0.65
- highly mobile players approach 0.95

---
# A.4 Combat Resolution

Combat occurs when opposing players occupy the same zone.
Each zone resolves a number of duels equal to: min(#Red_Players,#Blue_Players)

---
# A.5 Combat Score

Each player receives a **combat score**:

$combat_{score} = 0.28A + 0.16M + 0.14P + 0.12W + 0.10D + 0.08C + 0.05Ad + 0.07Ag$

Where:

| Symbol | Attribute       |
| ------ | --------------- |
| A      | aim             |
| M      | movement        |
| P      | positioning     |
| W      | awareness       |
| D      | decision_making |
| C      | consistency     |
| Ad     | adaptability    |
| Ag     | aggression      |

Aim is deliberately the dominant variable.

---
# A.6 Environmental Combat Modifiers

Combat score is adjusted according to environment.

---
## High Ground Bonus

If a player occupies a zone with positive elevation: $combat_{score} = combat_{score} + 0.10P + 0.05W$

Where:
- `P` = positioning
- `W` = awareness

Interpretation:
Players with strong positioning and awareness benefit more from high ground.

---

## Defender Base Bonus

If:
```
zone_type = BASE  
role = DEFENDER
```

then:
$combat_{score} = combat_{score} + 0.16P + 0.10R_d$

Where:
- $P$ = positioning
- $R_d$ = recovery_discipline

This models defensive familiarity with the base environment.

---
## Midfield Mobility Bonus
If:
```
zone_type ∈ {MID, CORRIDOR}  
role = MIDFIELD
```
then:
$combat_score = combat_{score} + 0.12M + 0.10Ad$

Where:
- `M` = movement
- `Ad` = adaptability

---
## Cover Modifier

Zones have a cover value $c ∈ [0,1]$.

Combat score is multiplied by:
$combat_{score} = combat_{score} (1 + 0.10c)$

---

# A.7 Behavioral Combat Modifiers

Behavior tendencies introduce additional stochasticity.

---
## Panic Under Pressure

```
If pressure > 0.6:
  combat_{score} ×= 0.86
```

---  
## Strong Under Objective Pressure  
  
If:  
- carrying flag  
- enemy flag taken  
- own flag missing  
  
then: 
`combat_score ×= 1.10`

---
## Inconsistent High Ceiling

Combat score multiplier:
`Uniform(0.80, 1.22)`

---
# A.8 Consistency Noise

All combat outcomes include attribute-dependent noise.

Noise magnitude:

$noise = \max(0.02, \frac{101 - consistency}{220})$

Final combat score:
$combat_{score} × Uniform(1 - noise, 1 + noise)$

Thus:
- high consistency → low variance
- low consistency → high variance

---

# A.9 Duel Outcome Probability

Given players A and B:

Let\
$S_A = combat_{score}(A)$\
$S_B = combat_{score}(B)$\

Probability A wins:

$P(A) = \frac{S_A}{S_A + S_B}$

A Bernoulli trial determines the duel winner.

---

# A.10 Flag Grab Probability

When a player reaches the enemy flag room:\

$grab\_{score} = 0.24M + 0.16R + 0.16O + 0.12W + 0.12D + 0.10P + 0.10Ad$

Where:

| Symbol | Attribute       |
| ------ | --------------- |
| M      | movement        |
| R      | route_knowledge |
| O      | objective_focus |
| W      | awareness       |
| D      | decision_making |
| P      | positioning     |
| Ad     | adaptability    |

Final grab probability:\
$P(grab) = clamp(grab_score / 100, 0.05, 0.95)$

---
# A.11 Flag Return Probability

If a player reaches a dropped friendly flag:

$return_{score} = 0.30R_d + 0.24W + 0.20O + 0.14P + 0.12D$

Where:
- $R_d$ = recovery_discipline

Final probability:\
$P(return) = clamp(return_score / 100, 0.05, 0.95)$

---

# A.12 Latent Skill Model

Ground truth player skill is generated from attributes and simulated performance.

---

## Core Skill

$CoreSkill = 0.18A + 0.16M + 0.14P + 0.14W + 0.12D + 0.08R + 0.08Ad + 0.10T$

Where:

- $T$ = teamplay

---

## Latent Skill

$LatentSkill = 0.60 CoreSkill + 0.25 RoleFit + 0.15 \frac{O + T}{2}$

Where:

- $O$ = objective_focus
- $T$ = teamplay

---

# A.13 Final Skill Score

The final ground truth score combines:

- latent attributes
- observed simulated performance

$CombinedScore = 0.65 LatentSkill + 0.35 PerfScore$

Players are ranked by `CombinedScore`.

Tier assignment:

| Tier    | Percentage |
| ------- | ---------- |
| Bronze  | 40%        |
| Silver  | 35%        |
| Gold    | 20%        |
| Diamond | 5%         |

---
# A.14 Design Philosophy

Three principles guided the simulator design:
### 1. Skill is latent
True skill is never directly observed.
### 2. Telemetry is noisy
Performance statistics include stochastic variability.
### 3. Roles matter
Objective and support behaviors are intentionally encoded so that: KDR alone is insufficient to rank players correctly.

This ensures that predictive models must capture **multi-dimensional gameplay behavior**.