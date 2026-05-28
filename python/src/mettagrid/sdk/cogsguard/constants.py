COGSGUARD_ROLE_NAMES = ("miner", "aligner", "scrambler", "scout")

COGSGUARD_ROLE_HP_THRESHOLDS = {
    "miner": 15,
    "aligner": 50,
    "scrambler": 30,
    "scout": 30,
    "unknown": 30,
}

COGSGUARD_GEAR_COSTS = {
    "miner": {"carbon": 1, "oxygen": 1, "germanium": 3, "silicon": 1},
    "aligner": {"carbon": 3, "oxygen": 1, "germanium": 1, "silicon": 1},
    "scrambler": {"carbon": 1, "oxygen": 3, "germanium": 1, "silicon": 1},
    "scout": {"carbon": 1, "oxygen": 1, "germanium": 1, "silicon": 3},
}

COGSGUARD_BOOTSTRAP_HUB_OFFSETS = {
    0: (0, 3),
    1: (0, 2),
    2: (3, 0),
    3: (2, 0),
    4: (-2, 0),
    5: (-3, 0),
    6: (0, -2),
    7: (0, -3),
}

COGSGUARD_JUNCTION_ALIGN_DISTANCE = 15
COGSGUARD_HUB_ALIGN_DISTANCE = 25
COGSGUARD_JUNCTION_AOE_RANGE = 10
