"""
TeamBot – Matrix bot for weekly football team generation.

Commands:
  !team               → Mannschaften aus letztem Vote generieren
  !spieler            → Spielerliste
  !spieler add …      → Spieler hinzufügen        (admin)
  !spieler set …      → Score manuell setzen       (admin)
  !spieler role …     → Hauptrolle ändern          (admin)
  !spieler del …      → Spieler deaktivieren       (admin)
  !ergebnis 3:2       → Matchergebnis eintragen    (admin)
  !vote               → Vote sofort starten        (admin)
  !scores             → Alle Scores anzeigen
  !help / !admin      → Hilfe                      (admin)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from nio import (
    AsyncClient,
    InviteMemberEvent,
    LoginResponse,
    RoomMessageText,
    RoomSendResponse,
    UnknownEvent,
)

from config import Config
from db import Database
from teams import balance_teams, format_teams, primary_score

logger = logging.getLogger(__name__)

VALID_ROLES = ("offensive", "defensive", "goalkeeper")

HELP_TEXT = """\
**TeamBot – Befehle**

**Alle Nutzer**
`!team`        – Teams aus dem aktuellen Vote generieren
`!spieler`     – Spielerliste mit Scores
`!scores`      – Alle Scores tabellarisch

**Admin**
`!spieler add @user:server Name [role]`   – Spieler anlegen
`!spieler set @user:server [role] [0-10]` – Score manuell setzen
`!spieler role @user:server [role]`       – Hauptrolle ändern
`!spieler del @user:server`               – Spieler deaktivieren
`!ergebnis 3:2`                           – Matchergebnis + Score-Update
`!vote`                                   – Vote jetzt starten

Rollen: `offensive` ⚔️ | `defensive` 🛡️ | `goalkeeper` 🧤
"""


class TeamBot:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.db_path)
        self.client = AsyncClient(config.homeserver, config.user_id)
        self.scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

        # In-memory state for the last generated teams (needed for !ergebnis)
        self._last_teams: Optional[Tuple[List[Dict], List[Dict]]] = None

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    async def start(self):
        await self.db.connect()

        resp = await self.client.login(self.config.password)
        if not isinstance(resp, LoginResponse):
            raise RuntimeError(f"Matrix login failed: {resp}")
        logger.info("Logged in as %s", self.config.user_id)

        self.client.add_event_callback(self._on_message, RoomMessageText)
        self.client.add_event_callback(self._on_reaction, UnknownEvent)
        self.client.add_event_callback(self._on_invite, InviteMemberEvent)

        self._setup_scheduler()
        self.scheduler.start()

        logger.info("Bot running – sync loop starting …")
        await self.client.sync_forever(timeout=30_000, full_state=True)

    def _setup_scheduler(self):
        cfg = self.config

        # Saturday 12:00 – start weekly vote
        self.scheduler.add_job(
            self._scheduled_vote,
            CronTrigger(day_of_week=cfg.vote_weekday,
                        hour=cfg.vote_hour,
                        minute=cfg.vote_minute),
            id="weekly_vote",
        )

        # Sunday 09:00 – auto-generate teams
        self.scheduler.add_job(
            self._scheduled_teams,
            CronTrigger(day_of_week=cfg.team_weekday,
                        hour=cfg.team_hour,
                        minute=cfg.team_minute),
            id="weekly_teams",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_admin(self, matrix_id: str) -> bool:
        return matrix_id in self.config.admin_users

    async def send(self, text: str) -> Optional[str]:
        """Send a plain + HTML message; return event_id on success."""
        content = {
            "msgtype": "m.text",
            "body": text,
            "format": "org.matrix.custom.html",
            "formatted_body": _md_to_html(text),
        }
        resp = await self.client.room_send(
            self.config.room_id, "m.room.message", content
        )
        if isinstance(resp, RoomSendResponse):
            return resp.event_id
        logger.error("send() failed: %s", resp)
        return None

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    async def _on_message(self, room, event):
        if room.room_id != self.config.room_id:
            return
        if event.sender == self.config.user_id:
            return

        body = event.body.strip()
        if not body.startswith("!"):
            return

        parts = body.split()
        cmd = parts[0].lower()

        try:
            match cmd:
                case "!team":
                    await self._cmd_team()
                case "!spieler":
                    await self._cmd_spieler(parts[1:], event.sender)
                case "!scores":
                    await self._cmd_scores()
                case "!ergebnis":
                    await self._cmd_ergebnis(parts[1:], event.sender)
                case "!vote":
                    if self.is_admin(event.sender):
                        await self._scheduled_vote()
                    else:
                        await self.send("❌ Keine Berechtigung.")
                case "!help" | "!admin":
                    if self.is_admin(event.sender):
                        await self.send(HELP_TEXT)
        except Exception as exc:
            logger.exception("Error in command %s", cmd)
            await self.send(f"❌ Fehler beim Ausführen von `{cmd}`: {exc}")

    async def _on_invite(self, room, event):
        """Auto-join any room the bot is invited to."""
        if event.membership != "invite":
            return
        if event.state_key != self.config.user_id:
            return
        logger.info("Invited to %s – joining …", room.room_id)
        resp = await self.client.join(room.room_id)
        if hasattr(resp, "room_id"):
            logger.info("Joined room %s", resp.room_id)
            # If this is the configured room, say hello
            if resp.room_id == self.config.room_id:
                await self.send("👋 TeamBot ist jetzt aktiv! Tippe `!help` für alle Befehle.")
        else:
            logger.error("Failed to join %s: %s", room.room_id, resp)

    async def _on_reaction(self, room, event):
        """Handle Matrix poll responses (MSC3381) and legacy emoji reactions."""
        if room.room_id != self.config.room_id:
            return
        if event.sender == self.config.user_id:
            return

        content = event.source.get("content", {})

        # ── Native Matrix Poll response ──
        if event.type in ("org.matrix.msc3381.poll.response", "m.poll.response"):
            relates_to = content.get("m.relates_to", {})
            poll_event_id = relates_to.get("event_id")
            vote = await self.db.get_vote_by_event(poll_event_id)
            if not vote or vote["closed"]:
                return
            answers = (
                content.get("org.matrix.msc3381.poll.response", {})
                or content.get("m.poll.response", {})
            ).get("answers", [])
            if "yes" in answers:
                await self.db.upsert_vote_response(vote["id"], event.sender, "yes")
                logger.info("Poll ✅  %s → vote %s", event.sender, vote["id"])
            elif "no" in answers:
                await self.db.upsert_vote_response(vote["id"], event.sender, "no")
                logger.info("Poll ❌  %s → vote %s", event.sender, vote["id"])
            return

        # ── Legacy emoji reaction ──
        if event.type != "m.reaction":
            return
        relates_to = content.get("m.relates_to", {})
        if relates_to.get("rel_type") != "m.annotation":
            return
        target_event_id = relates_to.get("event_id")
        key = relates_to.get("key", "")
        vote = await self.db.get_vote_by_event(target_event_id)
        if not vote or vote["closed"]:
            return
        if key == self.config.vote_yes:
            await self.db.upsert_vote_response(vote["id"], event.sender, "yes")
            logger.info("✅  %s → vote %s", event.sender, vote["id"])
        elif key == self.config.vote_no:
            await self.db.upsert_vote_response(vote["id"], event.sender, "no")
            logger.info("❌  %s → vote %s", event.sender, vote["id"])

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def _cmd_team(self):
        vote = await self.db.get_open_vote()
        if not vote:
            await self.send("⚠️ Kein offener Vote vorhanden. Bitte erst einen Vote starten (`!vote`).")
            return

        yes_ids = await self.db.get_vote_yes_players(vote["id"])
        if not yes_ids:
            await self.send("⚠️ Noch keine Zusagen im aktuellen Vote.")
            return

        players, unknown = [], []
        for mid in yes_ids:
            p = await self.db.get_player(mid)
            if p and p["active"]:
                players.append(p)
            else:
                unknown.append(mid)

        if len(players) < 2:
            await self.send(
                f"⚠️ Nur {len(players)} bekannte(r) Spieler mit Zusage – mindestens 2 benötigt."
            )
            return

        team1, team2 = balance_teams(players)
        self._last_teams = (team1, team2)

        msg = format_teams(team1, team2)
        if unknown:
            msg += f"\n\n⚠️ Nicht in DB: {', '.join(unknown)}"
        await self.send(msg)

    async def _cmd_spieler(self, args: List[str], sender: str):
        # No sub-command → list players
        if not args:
            await self._cmd_scores()
            return

        sub = args[0].lower()

        if sub == "add":
            if not self.is_admin(sender):
                return await self.send("❌ Keine Berechtigung.")
            # !spieler add @user:server Name [role]
            if len(args) < 3:
                return await self.send(
                    "Syntax: `!spieler add @user:server AnzeigeName [offensive|defensive|goalkeeper]`"
                )
            matrix_id, name = args[1], args[2]
            role = args[3].lower() if len(args) > 3 else "offensive"
            if role not in VALID_ROLES:
                return await self.send(f"❌ Ungültige Rolle. Erlaubt: {', '.join(VALID_ROLES)}")
            if await self.db.get_player(matrix_id):
                return await self.send(f"⚠️ Spieler `{matrix_id}` existiert bereits.")
            await self.db.add_player(matrix_id, name, role)
            await self.send(f"✅ **{name}** (`{matrix_id}`) als `{role}` hinzugefügt.")

        elif sub == "set":
            if not self.is_admin(sender):
                return await self.send("❌ Keine Berechtigung.")
            # !spieler set @user:server role score
            if len(args) < 4:
                return await self.send(
                    "Syntax: `!spieler set @user:server [offensive|defensive|goalkeeper] [0-10]`"
                )
            matrix_id, role = args[1], args[2].lower()
            if role not in VALID_ROLES:
                return await self.send(f"❌ Ungültige Rolle. Erlaubt: {', '.join(VALID_ROLES)}")
            try:
                score = round(min(10.0, max(0.0, float(args[3]))), 2)
            except ValueError:
                return await self.send("❌ Score muss eine Zahl zwischen 0 und 10 sein.")
            p = await self.db.get_player(matrix_id)
            if not p:
                return await self.send(f"❌ Spieler `{matrix_id}` nicht gefunden.")
            await self.db.update_player_score(matrix_id, role, score)
            await self.send(f"✅ **{p['display_name']}** – {role}: **{score:.2f}**")

        elif sub == "role":
            if not self.is_admin(sender):
                return await self.send("❌ Keine Berechtigung.")
            # !spieler role @user:server role
            if len(args) < 3:
                return await self.send(
                    "Syntax: `!spieler role @user:server [offensive|defensive|goalkeeper]`"
                )
            matrix_id, role = args[1], args[2].lower()
            if role not in VALID_ROLES:
                return await self.send(f"❌ Ungültige Rolle. Erlaubt: {', '.join(VALID_ROLES)}")
            p = await self.db.get_player(matrix_id)
            if not p:
                return await self.send(f"❌ Spieler `{matrix_id}` nicht gefunden.")
            await self.db.set_player_role(matrix_id, role)
            await self.send(f"✅ **{p['display_name']}** – Hauptrolle: **{role}**")

        elif sub == "del":
            if not self.is_admin(sender):
                return await self.send("❌ Keine Berechtigung.")
            if len(args) < 2:
                return await self.send("Syntax: `!spieler del @user:server`")
            p = await self.db.get_player(args[1])
            if not p:
                return await self.send(f"❌ Spieler `{args[1]}` nicht gefunden.")
            await self.db.deactivate_player(args[1])
            await self.send(f"✅ **{p['display_name']}** deaktiviert.")

        else:
            await self.send("Unbekannter Unterbefehl. Verfügbar: add, set, role, del")

    async def _cmd_scores(self):
        players = await self.db.get_all_players()
        if not players:
            return await self.send("Noch keine Spieler in der Datenbank.")

        role_emoji = {"offensive": "⚔️", "defensive": "🛡️", "goalkeeper": "🧤"}
        lines = ["**Spieler & Scores**", ""]
        lines.append(
            f"{'Name':<20} {'Rolle':<12} {'Wert':>5}  O      D      T"
        )
        lines.append("─" * 58)
        for p in players:
            emoji = role_emoji.get(p["primary_role"], "⚽")
            score = primary_score(p)
            lines.append(
                f"{emoji} {p['display_name']:<18} {p['primary_role']:<12} "
                f"{score:>5.2f}  "
                f"{p['score_offensive']:>5.2f}  "
                f"{p['score_defensive']:>5.2f}  "
                f"{p['score_goalkeeper']:>5.2f}"
            )
        await self.send("\n".join(lines))

    async def _cmd_ergebnis(self, args: List[str], sender: str):
        if not self.is_admin(sender):
            return await self.send("❌ Keine Berechtigung.")
        if not args:
            return await self.send("Syntax: `!ergebnis 3:2`")
        if not self._last_teams:
            return await self.send(
                "❌ Keine Teams gespeichert. Bitte erst `!team` ausführen."
            )

        try:
            s1, s2 = args[0].split(":")
            score1, score2 = int(s1), int(s2)
        except (ValueError, AttributeError):
            return await self.send("❌ Format: `!ergebnis 3:2`")

        team1, team2 = self._last_teams
        ids1 = [p["id"] for p in team1]
        ids2 = [p["id"] for p in team2]

        await self.db.save_match(score1, score2, ids1, ids2)
        await self.db.recalculate_scores(ids1 + ids2)

        # Result announcement
        if score1 > score2:
            result_line = "🏆 **Team 1 gewinnt!**"
        elif score2 > score1:
            result_line = "🏆 **Team 2 gewinnt!**"
        else:
            result_line = "🤝 **Unentschieden!**"

        t1_names = " · ".join(p["display_name"] for p in team1)
        t2_names = " · ".join(p["display_name"] for p in team2)

        await self.send(
            f"⚽ **Spielergebnis**\n\n"
            f"🔴 Team 1: **{score1}**  –  {t1_names}\n"
            f"🔵 Team 2: **{score2}**  –  {t2_names}\n\n"
            f"{result_line}\n\n"
            f"🔄 Scores wurden neu berechnet."
        )
        self._last_teams = None

    # ------------------------------------------------------------------
    # Scheduled jobs
    # ------------------------------------------------------------------

    async def _scheduled_vote(self):
        """Post the weekly vote as a native Matrix poll (MSC3381)."""
        now = datetime.now()

        # Next Sunday
        days_ahead = (6 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        if now.weekday() == 5:   # Saturday → game is tomorrow
            days_ahead = 1
        game_date = now + timedelta(days=days_ahead)

        game_date_str = game_date.strftime("%d.%m.%Y")
        cfg = self.config
        title = (
            f"Kicken Morgen, {game_date_str} um "
            f"{cfg.game_hour:02d}:{cfg.game_minute:02d} Uhr"
        )

        # MSC3381 poll – supported by Element, FluffyChat, Cinny etc.
        poll_content = {
            "msgtype": "m.text",
            "body": f"📊 {title}\n✅ Dabei / ❌ Nicht dabei",
            # Stable (Matrix 1.7+)
            "org.matrix.msc3381.poll.start": {
                "kind": "org.matrix.msc3381.poll.disclosed",
                "max_selections": 1,
                "question": {"body": f"⚽ {title}"},
                "answers": [
                    {"id": "yes", "org.matrix.msc3381.poll.answer.text": "✅ Dabei"},
                    {"id": "no",  "org.matrix.msc3381.poll.answer.text": "❌ Nicht dabei"},
                ],
            },
            # Unstable fallback (older Element versions)
            "m.poll.start": {
                "kind": "m.poll.disclosed",
                "max_selections": 1,
                "question": {"body": f"⚽ {title}"},
                "answers": [
                    {"id": "yes", "m.text": "✅ Dabei"},
                    {"id": "no",  "m.text": "❌ Nicht dabei"},
                ],
            },
        }

        resp = await self.client.room_send(
            self.config.room_id,
            "org.matrix.msc3381.poll.start",
            poll_content,
        )

        if isinstance(resp, RoomSendResponse):
            event_id = resp.event_id
            vote_date = game_date.strftime("%Y-%m-%d")
            vote_id = await self.db.create_vote(event_id, vote_date)
            logger.info(
                "Poll started – event_id=%s  vote_id=%d  date=%s",
                event_id, vote_id, vote_date,
            )
        else:
            logger.error("Failed to post poll: %s", resp)

    async def _scheduled_teams(self):
        """Auto-generate teams on Sunday 09:00."""
        logger.info("Scheduled team generation triggered")
        await self._cmd_team()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _md_to_html(text: str) -> str:
    """Minimal Markdown → HTML for Matrix formatted_body."""
    import re
    # **bold**
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    # `code`
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)
    # newlines
    text = text.replace("\n", "<br/>")
    return text
