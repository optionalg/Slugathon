"""Phase constants"""

# Master
SPLIT, MOVE, FIGHT, MUSTER = range(4)

# Battle
REINFORCE, MANEUVER, STRIKE, DRIFTDAMAGE, COUNTERSTRIKE, CLEANUP = range(6)

phase_names = {
    SPLIT:  "Split",
    MOVE:   "Move",
    FIGHT:  "Fight",
    MUSTER: "Muster",
    REINFORCE: "Reinforce",
    MANEUVER: "Maneuver",
    STRIKE: "Strike",
    DRIFTDAMAGE: "Drift damage",
    COUNTERSTRIKE: "Counterstrike",
    CLEANUP: "Cleanup",
}
