import json
import os

STATE_DIR = os.getenv('STATE_DIR', './')
_STATE_FILE = f'{STATE_DIR}/state.json'

def load_state():
    if not os.path.isfile(_STATE_FILE):
        save_state({})
    with open(_STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_state(state):
    with open(_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

def ensure_state(func):
    """Décorateur pour charger et sauver l'état automatiquement."""
    async def wrapper(room, message):
        st = load_state()
        try:
            # passe st en troisième argument positionnel
            result = await func(room, message, st)
        finally:
            save_state(st)
        return result
    return wrapper
