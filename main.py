"""TeamBot – Entry point."""

import asyncio
import logging
import os
import sys

from bot import TeamBot
from config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# nio.responses wirft harmlose Validation-Warnings bei bestimmten Synapse-Versionen
logging.getLogger("nio.responses").setLevel(logging.ERROR)


def create_config_interactive(path: str):
    """Create config.yml interactively if it doesn't exist."""
    print("\n📋 Keine config.yml gefunden – Setup-Assistent wird gestartet.\n")

    def ask(prompt: str, default: str = "") -> str:
        if default:
            val = input(f"  {prompt} [{default}]: ").strip()
            return val if val else default
        val = ""
        while not val:
            val = input(f"  {prompt}: ").strip()
        return val

    homeserver    = ask("Homeserver URL (z.B. https://matrix.org)")
    user_id       = ask("Bot User-ID (z.B. @teambot:matrix.org)")
    password      = ask("Bot Passwort")
    room_id       = ask("Hauptraum-ID (z.B. !abc123:matrix.org)")
    admin_room_id = ask("Admin-Raum-ID (z.B. !xyz456:matrix.org)")

    config_content = f"""\
# TeamBot Konfiguration – automatisch erstellt
homeserver: "{homeserver}"
user_id: "{user_id}"
password: "{password}"
room_id: "{room_id}"
admin_room_id: "{admin_room_id}"

db_path: "data/teambot.db"

# Vote: Samstag 12:00
vote_weekday: 5
vote_hour: 12
vote_minute: 0

# Teams: Sonntag 09:00
team_weekday: 6
team_hour: 9
team_minute: 0

# Spielzeit im Vote-Titel
game_hour: 10
game_minute: 0

vote_yes: "✅"
vote_no: "❌"
"""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(config_content)
    print(f"\n✅ config.yml erstellt: {path}\n")


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yml"

    if not os.path.exists(config_path):
        create_config_interactive(config_path)

    config = load_config(config_path)
    bot = TeamBot(config)
    try:
        await bot.start()
    finally:
        await bot.db.close()


if __name__ == "__main__":
    asyncio.run(main())
