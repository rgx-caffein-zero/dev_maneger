from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "servers.yaml"


def load_servers() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("servers", [])


def get_server(server_id: str) -> dict | None:
    for s in load_servers():
        if s.get("id") == server_id:
            return s
    return None
