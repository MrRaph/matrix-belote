import json
import os

STATE_DIR = os.getenv('STATE_DIR', './')
_STATE_FILE = f'{STATE_DIR}/state.json'

def load_state():
    """
    Charge l'état depuis le fichier JSON. Si le fichier n'existe pas ou est corrompu,
    initialise et retourne un état vide.
    """
    if not os.path.isfile(_STATE_FILE):
        save_state({})
        return {}
    try:
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        # Fichier vide ou invalide => réinitialisation
        save_state({})
        return {}

def save_state(state):
    """
    Sauvegarde l'état dans le fichier JSON.
    """
    with open(_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

def ensure_state(func):
    """
    Décorateur pour charger et sauvegarder automatiquement l'état autour
    de l'appel de la fonction.
    La fonction décorée doit accepter (room, message, st).
    """
    async def wrapper(room, message):
        st = load_state()
        try:
            # Appel de la fonction avec l'état chargé
            return await func(room, message, st)
        finally:
            # Sauvegarde même en cas d'exception
            save_state(st)
    return wrapper