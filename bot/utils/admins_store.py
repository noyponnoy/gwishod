import json
import os

ADMINS_FILE = os.path.join(os.path.dirname(__file__), "..", "admins.json")


def _load() -> list[int]:
    try:
        with open(ADMINS_FILE, "r") as f:
            data = json.load(f)
            return data.get("admins", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(admins: list[int]):
    with open(ADMINS_FILE, "w") as f:
        json.dump({"admins": admins}, f)


def get_all_admins() -> list[int]:
    return _load()


def add_admin(tg_id: int) -> bool:
    admins = _load()
    if tg_id in admins:
        return False
    admins.append(tg_id)
    _save(admins)
    return True


def remove_admin(tg_id: int, root_admins: list[int]) -> bool:
    if tg_id in root_admins:
        return False
    admins = _load()
    if tg_id not in admins:
        return False
    admins.remove(tg_id)
    _save(admins)
    return True


def is_admin(tg_id: int, root_admins: list[int]) -> bool:
    return tg_id in root_admins or tg_id in _load()
