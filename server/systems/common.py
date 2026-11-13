"""Shared helpers for the mock downstream systems."""
import json
import os
import threading

LOCK = threading.RLock()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def load_json(system: str, filename: str, default=None):
    path = os.path.join(DATA_DIR, system, filename)
    if not os.path.exists(path):
        return [] if default is None else default
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def money(value) -> float:
    return round(float(value) + 0.0, 2)


def today():
    """
    The lab clock. Frozen at the as-at date of the dataset (server/data/as_at.json)
    so every team gets the same answers whenever the workshop runs. Falls back to
    the real date if the file is missing.
    """
    import datetime
    path = os.path.join(DATA_DIR, 'as_at.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fh:
            return datetime.date.fromisoformat(json.load(fh)['as_at'])
    return datetime.date.today()
