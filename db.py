"""
Database layer – SQLite via aiosqlite.

Tables:
  players            – Spieler mit 3 Score-Feldern + Hauptrolle
  matches            – Matchergebnisse
  match_participations – Score je Spieler je Match (Grundlage Neuberechnung)
  votes              – Wöchentliche Abstimmungsnachrichten
  vote_responses     – Reaktionen der Spieler
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS players (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matrix_id       TEXT    UNIQUE NOT NULL,
    display_name    TEXT    NOT NULL,
    score_offensive REAL    NOT NULL DEFAULT 5.0,
    score_defensive REAL    NOT NULL DEFAULT 5.0,
    score_goalkeeper REAL   NOT NULL DEFAULT 5.0,
    primary_role    TEXT    NOT NULL DEFAULT 'offensive',
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS matches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    team1_score         INTEGER NOT NULL,
    team2_score         INTEGER NOT NULL,
    team1_player_ids    TEXT    NOT NULL,   -- JSON array of player.id
    team2_player_ids    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS match_participations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(id),
    player_id   INTEGER NOT NULL REFERENCES players(id),
    team        INTEGER NOT NULL,   -- 1 or 2
    goal_diff   INTEGER NOT NULL,   -- positive = team won
    match_score REAL    NOT NULL,   -- 0–10 derived from goal_diff
    UNIQUE(match_id, player_id)
);

CREATE TABLE IF NOT EXISTS votes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT    UNIQUE,     -- Matrix event_id of the poll message
    vote_date   TEXT    NOT NULL,   -- Game date YYYY-MM-DD
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    closed      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vote_responses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vote_id      INTEGER NOT NULL REFERENCES votes(id),
    matrix_id    TEXT    NOT NULL,
    response     TEXT    NOT NULL,  -- 'yes' or 'no'
    responded_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(vote_id, matrix_id)
);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("Database ready: %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------

    async def add_player(
        self, matrix_id: str, display_name: str, role: str = "offensive"
    ) -> int:
        async with self._db.execute(
            "INSERT INTO players (matrix_id, display_name, primary_role) VALUES (?,?,?)",
            (matrix_id, display_name, role),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid  # type: ignore

    async def get_player(self, matrix_id: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM players WHERE matrix_id = ?", (matrix_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_player_by_id(self, player_id: int) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM players WHERE id = ?", (player_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_all_players(self, active_only: bool = True) -> List[Dict]:
        sql = "SELECT * FROM players"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY display_name COLLATE NOCASE"
        async with self._db.execute(sql) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def update_player_score(self, matrix_id: str, role: str, score: float):
        col = f"score_{role}"
        await self._db.execute(
            f"UPDATE players SET {col} = ? WHERE matrix_id = ?",
            (round(score, 2), matrix_id),
        )
        await self._db.commit()

    async def set_player_role(self, matrix_id: str, role: str):
        await self._db.execute(
            "UPDATE players SET primary_role = ? WHERE matrix_id = ?",
            (role, matrix_id),
        )
        await self._db.commit()

    async def deactivate_player(self, matrix_id: str):
        await self._db.execute(
            "UPDATE players SET active = 0 WHERE matrix_id = ?", (matrix_id,)
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Votes
    # ------------------------------------------------------------------

    async def create_vote(self, event_id: str, vote_date: str) -> int:
        # Close all open votes before creating a new one
        await self._db.execute("UPDATE votes SET closed = 1 WHERE closed = 0")
        async with self._db.execute(
            "INSERT INTO votes (event_id, vote_date) VALUES (?,?)",
            (event_id, vote_date),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid  # type: ignore

    async def get_open_vote(self) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM votes WHERE closed = 0 ORDER BY created_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_vote_by_event(self, event_id: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM votes WHERE event_id = ?", (event_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def upsert_vote_response(
        self, vote_id: int, matrix_id: str, response: str
    ):
        await self._db.execute(
            """INSERT INTO vote_responses (vote_id, matrix_id, response)
               VALUES (?,?,?)
               ON CONFLICT(vote_id, matrix_id)
               DO UPDATE SET response = excluded.response,
                             responded_at = datetime('now')""",
            (vote_id, matrix_id, response),
        )
        await self._db.commit()

    async def get_vote_yes_players(self, vote_id: int) -> List[str]:
        async with self._db.execute(
            "SELECT matrix_id FROM vote_responses WHERE vote_id = ? AND response = 'yes'",
            (vote_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def close_vote(self, vote_id: int):
        await self._db.execute(
            "UPDATE votes SET closed = 1 WHERE id = ?", (vote_id,)
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Matches & score recalculation
    # ------------------------------------------------------------------

    async def save_match(
        self,
        team1_score: int,
        team2_score: int,
        team1_ids: List[int],
        team2_ids: List[int],
    ) -> int:
        """Persist match and participation records; returns match_id."""
        async with self._db.execute(
            """INSERT INTO matches (team1_score, team2_score,
                                   team1_player_ids, team2_player_ids)
               VALUES (?,?,?,?)""",
            (
                team1_score,
                team2_score,
                json.dumps(team1_ids),
                json.dumps(team2_ids),
            ),
        ) as cur:
            match_id = cur.lastrowid

        goal_diff_t1 = team1_score - team2_score
        goal_diff_t2 = -goal_diff_t1

        for pid in team1_ids:
            ms = _goal_diff_to_score(goal_diff_t1)
            await self._db.execute(
                """INSERT INTO match_participations
                   (match_id, player_id, team, goal_diff, match_score)
                   VALUES (?,?,1,?,?)""",
                (match_id, pid, goal_diff_t1, ms),
            )
        for pid in team2_ids:
            ms = _goal_diff_to_score(goal_diff_t2)
            await self._db.execute(
                """INSERT INTO match_participations
                   (match_id, player_id, team, goal_diff, match_score)
                   VALUES (?,?,2,?,?)""",
                (match_id, pid, goal_diff_t2, ms),
            )

        await self._db.commit()
        return match_id  # type: ignore

    async def recalculate_scores(self, player_ids: List[int]):
        """
        Recalculate each player's PRIMARY score using:
          50% all-time average match_score
          30% last-3-months average match_score
          20% most-recent match_score
        """
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

        for pid in player_ids:
            # All-time average
            avg_all = await self._scalar(
                "SELECT AVG(match_score) FROM match_participations WHERE player_id=?",
                (pid,),
                default=5.0,
            )
            # Last-3-months average
            avg_3m = await self._scalar(
                """SELECT AVG(mp.match_score)
                   FROM match_participations mp
                   JOIN matches m ON mp.match_id = m.id
                   WHERE mp.player_id = ? AND m.played_at >= ?""",
                (pid, cutoff),
                default=avg_all,
            )
            # Last match
            last = await self._scalar(
                """SELECT mp.match_score
                   FROM match_participations mp
                   JOIN matches m ON mp.match_id = m.id
                   WHERE mp.player_id = ?
                   ORDER BY m.played_at DESC LIMIT 1""",
                (pid,),
                default=avg_all,
            )

            new_score = round(
                avg_all * 0.50 + avg_3m * 0.30 + last * 0.20, 2
            )
            new_score = min(10.0, max(0.0, new_score))

            # Which column to update?
            async with self._db.execute(
                "SELECT primary_role FROM players WHERE id=?", (pid,)
            ) as cur:
                row = await cur.fetchone()
                role = row[0] if row else "offensive"

            await self._db.execute(
                f"UPDATE players SET score_{role} = ? WHERE id = ?",
                (new_score, pid),
            )

        await self._db.commit()
        logger.info("Scores recalculated for %d players", len(player_ids))

    async def get_last_match(self) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM matches ORDER BY played_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["team1_player_ids"] = json.loads(d["team1_player_ids"])
            d["team2_player_ids"] = json.loads(d["team2_player_ids"])
            return d

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _scalar(self, sql: str, params: tuple, default: float) -> float:
        async with self._db.execute(sql, params) as cur:
            row = await cur.fetchone()
            val = row[0] if row else None
            return float(val) if val is not None else default


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _goal_diff_to_score(goal_diff: int) -> float:
    """
    Map team goal difference to a 0–10 match score.
      -5 or worse → 0
       0           → 5
      +5 or better → 10
    """
    return float(min(10, max(0, 5 + goal_diff)))
