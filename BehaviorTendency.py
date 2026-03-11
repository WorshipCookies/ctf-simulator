from enum import Enum

class BehaviorTendency(str, Enum):
    OVEREXTENDS_OFTEN = "overextends often"
    TOO_PASSIVE = "too passive"
    SELFISH_FRAGGER = "selfish fragger"
    DISCIPLINED_ANCHOR = "disciplined anchor"
    PANIC_UNDER_PRESSURE = "panic under pressure"
    STRONG_UNDER_OBJECTIVE_PRESSURE = "strong under objective pressure"
    INCONSISTENT_HIGH_CEILING = "inconsistent but high ceiling"