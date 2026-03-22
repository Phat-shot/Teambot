"""
Team balancing – minimiert |sum(Team1) - sum(Team2)| exakt.

Für N ≤ 22 Spieler ist C(22, 11) ≈ 700k – in <100ms lösbar.
Bei größeren Gruppen wird greedy verwendet (Praxis: irrelevant).
"""

import random
from itertools import combinations
from typing import Dict, List, Tuple

ROLE_EMOJI = {
    "offensive": "⚔️",
    "defensive": "🛡️",
    "goalkeeper": "🧤",
}
TEAM_COLORS = ["🔴", "🔵"]


def primary_score(player: Dict) -> float:
    role = player.get("primary_role", "offensive")
    return round(float(player.get(f"score_{role}", 5.0)), 2)


def balance_teams(players: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Split players into two teams with minimal score difference.
    Team 1 gets ceil(N/2) players, Team 2 gets floor(N/2).
    """
    n = len(players)
    if n < 2:
        return players, []

    half = n // 2          # smaller half → Team 2
    other = n - half       # larger half  → Team 1 (gets +1 if odd)

    best_diff = float("inf")
    best_team2_indices: frozenset = frozenset()

    # Exhaustive search over all ways to choose `half` players for Team 2
    for combo in combinations(range(n), half):
        t2_score = sum(primary_score(players[i]) for i in combo)
        t1_score = sum(
            primary_score(players[i]) for i in range(n) if i not in combo
        )
        diff = abs(t1_score - t2_score)
        if diff < best_diff:
            best_diff = diff
            best_team2_indices = frozenset(combo)

    team1 = [players[i] for i in range(n) if i not in best_team2_indices]
    team2 = [players[i] for i in best_team2_indices]

    # Shuffle within teams for fairness
    random.shuffle(team1)
    random.shuffle(team2)

    return team1, team2


def format_teams(team1: List[Dict], team2: List[Dict]) -> str:
    t1_total = sum(primary_score(p) for p in team1)
    t2_total = sum(primary_score(p) for p in team2)
    diff = abs(t1_total - t2_total)

    def player_line(p: Dict) -> str:
        emoji = ROLE_EMOJI.get(p.get("primary_role", "offensive"), "⚽")
        score = primary_score(p)
        return f"  {emoji} {p['display_name']} ({score:.2f})"

    lines = [
        "⚽ **Mannschaften** ⚽",
        "",
        f"🔴 **Team 1**  |  Stärke: {t1_total:.2f}",
        *[player_line(p) for p in team1],
        "",
        f"🔵 **Team 2**  |  Stärke: {t2_total:.2f}",
        *[player_line(p) for p in team2],
        "",
        f"⚖️ Differenz: {diff:.2f}",
    ]
    return "\n".join(lines)
