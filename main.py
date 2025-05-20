import os
import simplematrixbotlib as botlib
from belote import BeloteGame
import state

# -- Configuration du bot --
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
    if not m.prefix() or not m.command('help'):
        return
    txt = (
        "Commandes disponibles :\n"
        f"- {PREFIX}start : démarrer une nouvelle donne\n"
        f"- {PREFIX}hand : afficher votre main privée\n"
        f"- {PREFIX}bid <points> <suit|SA|TA> : enchérir\n"
        f"- {PREFIX}pass : passer\n"
        f"- {PREFIX}coinche : coincher un contrat adverse\n"
        f"- {PREFIX}surcoinche : surcoincher\n"
        f"- {PREFIX}play <card> : jouer une carte (phase de jeu)\n"
        f"- {PREFIX}trick : voir pli en cours\n"
        f"- {PREFIX}score : afficher scores de la partie"
    )
    await bot.api.send_text_message(room.room_id, txt)

@bot.listener.on_message_event
@state.ensure_state
async def on_start(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command('start'):
        return
    key = room.room_id
    human = message.sender
    bots = [f"Bot{i}" for i in range(1, 4)]
    players = [human] + bots
    # Initialisation du jeu
    game = BeloteGame(key, players)
    game.start()
    # Persister l'état sérialisable
    st[key] = game.to_dict()
    # Affichage schématique de la table
    table_txt = (
        f"Table:"
        f"   Nord : {players[2]}"
        f"Ouest : {players[1]}    Est : {players[3]}"
        f"   Sud : {players[0]} (vous)"
        f"Partenaire : {players[2]}"
    )
    await bot.api.send_text_message(room.room_id, table_txt)
    # Envoi de la main en privé
    hand = ' '.join(sorted(game.hands[human]))
    await bot.api.send_text_message(human, f"Votre main : {hand}")
    # Démarrage des enchères automatiques des bots jusqu'à votre tour
    auction = game.auction
    import random
    bot_msgs = []
    while not auction.finished and auction.players[auction.current] != human:
        player = auction.players[auction.current]
        # bot décide action
        if auction.best is None:
            action = random.choice(['pass', 'bid'])
        else:
            action = random.choice(['pass', 'bid', 'pass'])
        if action == 'pass':
            auction.propose(player, 'pass')
            bot_msgs.append(f"{player} a PASSÉ.")
        else:
            pts = random.choice(range((auction.best['points'] if auction.best else 80) + 10, 170, 10))
            suit = random.choice(['♠','♥','♦','♣','SA','TA'])
            try:
                auction.propose(player, 'bid', pts, suit)
                bot_msgs.append(f"{player} a ENCHÉRI : {pts}{suit}.")
            except Exception:
                auction.propose(player, 'pass')
                bot_msgs.append(f"{player} a PASSÉ.")
        st[key] = game.to_dict()
    # Envoi des actions des bots
    for msg in bot_msgs:
        await bot.api.send_text_message(room.room_id, msg)
    # Indication du prochain à parler
    if auction.finished:
        # résumé
        txt = f"Enchères terminées :{auction.summary()}"
        if auction.best:
            best = auction.best
            txt += f"Contrat provisoire -> {best['points']}{best['suit']} par {best['player']}"
        else:
            txt += "Tout le monde a passé !"
        await bot.api.send_text_message(room.room_id, txt)
    else:
        await bot.api.send_text_message(room.room_id, f"À vous de PARLER.")
@bot.listener.on_message_event
@state.ensure_state
async def on_auction(room, message, st):
    m = match(room, message)
    if not m.prefix():
        return
    key = room.room_id
    if key not in st:
        return
    # Reconstruction depuis le dict serialisé
    game = BeloteGame.from_dict(key, st[key])
    if game.phase != 'auction':
        return
    player = message.sender
    cmd = m.command()
    try:
        if cmd == 'pass':
            redeal = game.process_auction(player, 'pass')
        elif cmd == 'bid':
            pts = int(m.args()[0]); suit = m.args()[1]
            redeal = game.process_auction(player, 'bid', pts, suit)
        elif cmd == 'coinche':
            redeal = game.process_auction(player, 'coinche')
        elif cmd == 'surcoinche':
            redeal = game.process_auction(player, 'surcoinche')
        else:
            return
    except Exception as e:
        await bot.api.send_text_message(room.room_id, f"Erreur enchère : {e}")
        return
    # Message récapitulatif
    txt = f"Enchères en cours :\n{game.auction.summary()}"
    if game.auction.finished:
        if redeal == 'redeal':
            txt += "\nTout le monde a passé, redistribution et nouveau tour !"
        else:
            c = game.contract
            txt += f"\nContrat -> {c['points']}{c['suit']} par {c['player']}"
            if game.auction.coinched_by:
                txt += f" (coinché par {game.auction.coinched_by})"
            if game.auction.surcoinched_by:
                txt += f" (surcoinché par {game.auction.surcoinched_by})"
            first = game.players[game.turn_idx]
            txt += f"\nPhase de jeu : {first} commence."    
    else:
        nextp = game.players[game.auction.current]
        txt += f"\nÀ {nextp} de parler."
    await bot.api.send_markdown_message(room.room_id, txt)
    # Re-sauvegarde state serialisable
    st[key] = game.to_dict()

if __name__ == '__main__':
    bot.run()
