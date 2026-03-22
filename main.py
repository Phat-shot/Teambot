"""TeamBot – Entry point."""

import asyncio
import logging
import sys

from bot import TeamBot
from config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yml"
    config = load_config(config_path)
    bot = TeamBot(config)
    try:
        await bot.start()
    finally:
        await bot.db.close()


if __name__ == "__main__":
    asyncio.run(main())
