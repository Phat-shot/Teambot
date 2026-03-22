import os
import yaml
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # Matrix credentials
    homeserver: str
    user_id: str
    password: str
    room_id: str
    admin_users: List[str]

    # Storage
    db_path: str = "data/teambot.db"

    # Vote schedule: Saturday 12:00
    vote_weekday: int = 5   # 0=Mon … 6=Sun
    vote_hour: int = 12
    vote_minute: int = 0

    # Team generation: Sunday 09:00
    team_weekday: int = 6
    team_hour: int = 9
    team_minute: int = 0

    # Game time shown in vote title
    game_hour: int = 10
    game_minute: int = 0

    # Reaction emojis
    vote_yes: str = "✅"
    vote_no: str = "❌"


def load_config(path: str = "config.yml") -> Config:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config(**data)
