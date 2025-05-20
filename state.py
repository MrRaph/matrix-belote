import json
import os

STATE_DIR = os.getenv('STATE_DIR', './')
_STATE_FILE = f'{STATE_DIR}/state.json'

def load_state():
    # Si le fichier n'existe pas, on initialise un état vide
    if not os.path.isfile(_STATE_FILE):
        save_state({})
        return {}
    try:
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        # Fichier corrompu ou vide : on réinitialise
        save_state({})
        return {}

def save_state(state):
    with open(_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

def ensure_state(func):
    """Décorateur pour charger et sauver l'état automatiquement."""
    async def wrapper(room, message):
        st = load_state()
        try:
            return await func(room, message, st)
        finally:
            save_state(st)
    return wrapper