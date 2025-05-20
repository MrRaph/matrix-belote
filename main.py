"""Matrix Bot pour jouer à la Belote coinchée en chat."""
import os
import simplematrixbotlib as botlib
from belote import BeloteGame
import state

# -- Initialisation du bot --
creds = botlib.Creds(
    homeserver=os.environ.get('HOMESERVER'),
    username=os.environ.get('USERNAME'),
    password=os.environ.get('PASSWORD'),
    access_token=os.environ.get('ACCESS_TOKEN')
)
bot = botlib.Bot(creds)
PREFIX = os.environ.get('PREFIX', 'b!')

def match(room, message):
    return botlib.MessageMatch(room, message, bot, PREFIX)

@bot.listener.on_message_event
async def help_message(room, message):
    m = match(room, message)
    if not m.prefix() or not (m.command("help") or m.command("h")):
        return
    txt = (
        "## matrix-belote\n"
        "Commandes disponibles :\n"
        f"- `{PREFIX}help` (ou `h`) : aide\n"
        f"- `{PREFIX}start` (ou `s`) : nouvelle partie\n"
        f"- `{PREFIX}bid <points> <suit>` : enchérir (ex. `bid 80 hearts`)\n"
        f"- `{PREFIX}pass` : passer\n"
        f"- `{PREFIX}coinche` / `{PREFIX}surcoinche`\n"
        f"- `{PREFIX}play <card>` : jouer une carte (ex. `play 10♠`)\n"
        f"- `{PREFIX}hand` : afficher votre main\n"
        f"- `{PREFIX}trick` : pli actuel\n"
        f"- `{PREFIX}score` : scores"
    )
    await bot.api.send_markdown_message(room.room_id, txt)

@bot.listener.on_message_event
@state.ensure_state
async def start_game(room, message, st):
    m = match(room, message)
    if not m.prefix() or not (m.command("start") or m.command("s")):
        return
    # Création d'une partie
    game = BeloteGame(room.room_id)
    game.start_game()
    st[room.room_id] = game.to_dict()
    # Affiche l’état de la partie ET votre main
    hand = " ".join(sorted(game.hands[game.players[0]]))
    await bot.api.send_markdown_message(
        room.room_id,
        f"Nouvelle partie lancée ! Vous êtes **SOUTH**.\n"
        f"- Votre main : `{hand}`\n"
        f"- Enchérissez avec `{PREFIX}bid <points> <suit>` ou `{PREFIX}pass`."
    )

@bot.listener.on_message_event
@state.ensure_state
async def handle_bid(room, message, st):
    m = match(room, message)
    if not m.prefix():
        return
    key = room.room_id
    if key not in st:
        return
    game = BeloteGame.from_dict(key, st[key])
    # Traitement de votre enchère ou passe
    if m.command("pass"):
        bid_res = game.process_user_bid(0, None)
        user_txt = "Vous avez **passé**."
    elif m.command("bid"):
        args = m.args()
        if len(args) != 2 or not args[0].isdigit() or args[1] not in ['♠','♥','♦','♣']:
            await bot.api.send_text_message(
                room.room_id,
                f"Usage: `{PREFIX}bid <points> <suit>` (points multiple de 10, suit un de ♠♥♦♣)"
            )
            return
        pts = int(args[0])
        suit = args[1]
        bid_res = game.process_user_bid(pts, suit)
        user_txt = f"Vous avez **enchéri** : {pts}{suit}."
    else:
        return

    # Construire le résumé des enchères
    bids_lines = []
    for b in game.bids:
        if b['bid'] == 'PASS':
            bids_lines.append(f"- {b['player']}: PASS")
        else:
            pts, suit = b['bid']
            bids_lines.append(f"- {b['player']}: {pts}{suit}")
    bids_txt = "\n".join(bids_lines)

    # Déterminer le contrat final
    if bid_res:
        contract_txt = f"**Contrat** : {bid_res['points']}{bid_res['suit']} par {bid_res['player']}."
    else:
        contract_txt = "Tout le monde a passé ! Relancez la partie avec `b!start`."

    # Envoi du message complet
    await bot.api.send_markdown_message(
        room.room_id,
        f"{user_txt}\n\n"
        f"**Enchères :**\n{bids_txt}\n\n"
        f"{contract_txt}"
    )

    st[key] = game.to_dict()

@bot.listener.on_message_event
@state.ensure_state
async def play_card(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command("play"):
        return
    key = room.room_id
    if key not in st:
        await bot.api.send_text_message(room.room_id, "Pas de partie en cours, faites `b!start` d'abord.")
        return
    args = m.args()
    if len(args) != 1:
        return
    card = args[0]
    game = BeloteGame.from_dict(key, st[key])
    try:
        winner = game.play_card(game.players[0], card)
    except ValueError:
        await bot.api.send_text_message(room.room_id, f"Carte invalide : {card}")
        return
    # Annonce du gagnant du pli
    await bot.api.send_text_message(room.room_id, f"Pli remporté par {winner}.")
    # Si plus de cartes, fin
    if not game.hands[game.players[0]]:
        scores = game.compute_scores()
        await bot.api.send_text_message(
            room.room_id,
            f"Fin de la partie ! Scores → NS: {scores['NS']} pts, WE: {scores['WE']} pts"
        )
        del st[key]
    else:
        # Prochain tour
        st[key] = game.to_dict()

@bot.listener.on_message_event
@state.ensure_state
async def show_hand(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command("hand"):
        return
    key = room.room_id
    if key in st:
        game = BeloteGame.from_dict(key, st[key])
        hand = " ".join(sorted(game.hands[game.players[0]]))
        await bot.api.send_text_message(room.room_id, f"Votre main : {hand}")

@bot.listener.on_message_event
@state.ensure_state
async def show_trick(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command("trick"):
        return
    key = room.room_id
    if key in st:
        game = BeloteGame.from_dict(key, st[key])
        if not game.trick:
            await bot.api.send_text_message(room.room_id, "Aucun pli en cours.")
        else:
            txt = "Pli actuel :\n" + "\n".join(f"{p}: {c}" for p,c in game.trick)
            await bot.api.send_text_message(room.room_id, txt)

@bot.listener.on_message_event
@state.ensure_state
async def show_score(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command("score"):
        return
    key = room.room_id
    if key in st:
        game = BeloteGame.from_dict(key, st[key])
        sc = game.scores
        await bot.api.send_text_message(room.room_id, f"Scores → NS: {sc['NS']} pts, WE: {sc['WE']} pts")

if __name__ == '__main__':
    bot.run()
