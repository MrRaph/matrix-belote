import os
import random
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


async def ensure_dm(room):
    """Vérifie qu'on est en message privé (max 2 participants)."""
    resp = await bot.async_client.joined_members(room.room_id)
    if len(resp.members) > 2:
        await bot.api.send_text_message(
            room.room_id,
            "❌ Je ne fonctionne qu'en messages privés. Je quitte ce salon."
        )
        await bot.api.leave_room(room.room_id)
        return False
    return True


@bot.listener.on_message_event
async def help_message(room, message):
    m = match(room, message)
    if not m.prefix() or not m.command('help'):
        return
    if not await ensure_dm(room):
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
    if not await ensure_dm(room):
        return

    key = room.room_id
    human = message.sender
    bots = [f"Bot{i}" for i in range(1, 4)]
    players = [human] + bots

    game = BeloteGame(key, players)
    game.start()
    st[key] = game.to_dict()

    # Affichage de la table et du partenaire
    table_txt = (
        "Table :\n"
        f"   Nord : {players[2]}\n"
        f"Ouest : {players[1]}    Est : {players[3]}\n"
        f"   Sud : {players[0]} (vous)\n"
        f"Partenaire : {players[2]}"
    )
    await bot.api.send_text_message(room.room_id, table_txt)

    # Affichage immédiat de la main
    hand = ' '.join(sorted(game.hands[human]))
    await bot.api.send_text_message(room.room_id, f"Votre main : {hand}")

    # Enchères automatiques des bots jusqu'à votre tour
    auction = game.auction
    bot_msgs = []
    while not auction.finished and auction.players[auction.current] != human:
        player = auction.players[auction.current]
        if auction.best is None:
            action = random.choice(['pass', 'bid'])
        else:
            action = 'pass' if auction.best['points'] >= 160 else random.choice(['pass', 'pass', 'bid'])
        if action == 'pass':
            auction.propose(player, 'pass')
            bot_msgs.append(f"{player} a PASSÉ.")
        else:
            min_pts = auction.best['points'] + 10 if auction.best else 80
            valid = [p for p in range(min_pts, 161, 10)]
            if not valid:
                auction.propose(player, 'pass')
                bot_msgs.append(f"{player} a PASSÉ.")
            else:
                pts = random.choice(valid)
                suit = random.choice(['♠', '♥', '♦', '♣', 'SA', 'TA'])
                try:
                    auction.propose(player, 'bid', pts, suit)
                    bot_msgs.append(f"{player} a ENCHÉRI : {pts}{suit}.")
                except ValueError:
                    auction.propose(player, 'pass')
                    bot_msgs.append(f"{player} a PASSÉ.")
        st[key] = game.to_dict()

    for msg in bot_msgs:
        await bot.api.send_text_message(room.room_id, msg)

    # Résumé des enchères
    summary = auction.summary()
    txt = f"Enchères :\n{summary}"
    if auction.finished:
        if auction.best:
            b = auction.best
            txt += f"\nContrat -> {b['points']}{b['suit']} par {b['player']}"
        else:
            txt += "\nTout le monde a passé !"
        txt += f"\nPhase de jeu : {game.players[game.turn_idx]} commence."
    else:
        txt += "\nÀ vous de PARLER."
    await bot.api.send_text_message(room.room_id, txt)
    st[key] = game.to_dict()


@bot.listener.on_message_event
@state.ensure_state
async def on_auction(room, message, st):
    m = match(room, message)
    if not m.prefix():
        return
    if not await ensure_dm(room):
        return

    key = room.room_id
    if key not in st:
        return

    game = BeloteGame.from_dict(key, st[key])
    if game.phase != 'auction':
        return

    human = message.sender
    try:
        if m.command('pass'):
            redeal = game.process_auction(human, 'pass')
        elif m.command('bid'):
            args = m.args()
            redeal = game.process_auction(human, 'bid', int(args[0]), args[1])
        elif m.command('coinche'):
            redeal = game.process_auction(human, 'coinche')
        elif m.command('surcoinche'):
            redeal = game.process_auction(human, 'surcoinche')
        else:
            return
    except Exception as e:
        await bot.api.send_text_message(room.room_id, f"Erreur enchère : {e}")
        return

    st[key] = game.to_dict()

    # Enchères automatiques des bots après votre action
    auction = game.auction
    bot_msgs = []
    while not auction.finished and auction.players[auction.current] != human:
        player = auction.players[auction.current]
        if auction.best is None:
            action = random.choice(['pass', 'bid'])
        else:
            action = 'pass' if auction.best['points'] >= 160 else random.choice(['pass', 'pass', 'bid'])
        if action == 'pass':
            auction.propose(player, 'pass')
            bot_msgs.append(f"{player} a PASSÉ.")
        else:
            min_pts = auction.best['points'] + 10 if auction.best else 80
            valid = [p for p in range(min_pts, 161, 10)]
            if not valid:
                auction.propose(player, 'pass')
                bot_msgs.append(f"{player} a PASSÉ.")
            else:
                pts = random.choice(valid)
                suit = random.choice(['♠', '♥', '♦', '♣', 'SA', 'TA'])
                try:
                    auction.propose(player, 'bid', pts, suit)
                    bot_msgs.append(f"{player} a ENCHÉRI : {pts}{suit}.")
                except ValueError:
                    auction.propose(player, 'pass')
                    bot_msgs.append(f"{player} a PASSÉ.")
        st[key] = game.to_dict()

    # Résumé et transition vers jeu
    summary = auction.summary()
    txt = f"Enchères :\n{summary}"
    for msg in bot_msgs:
        txt += f"\n{msg}"
    if auction.finished:
        if auction.best:
            b = auction.best
            txt += f"\nContrat -> {b['points']}{b['suit']} par {b['player']}"
        else:
            txt += "\nTout le monde a passé !"
        txt += f"\nPhase de jeu : {game.players[game.turn_idx]} commence."
    else:
        txt += "\nÀ vous de PARLER."
    await bot.api.send_text_message(room.room_id, txt)
    st[key] = game.to_dict()


@bot.listener.on_message_event
@state.ensure_state
async def show_hand(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command('hand'):
        return
    if not await ensure_dm(room):
        return

    key = room.room_id
    game = BeloteGame.from_dict(key, st.get(key, {}))
    hand = game.hands.get(message.sender, [])
    hand_txt = ' '.join(sorted(hand)) if hand else '(aucune)'
    await bot.api.send_text_message(room.room_id, f"Votre main : {hand_txt}")


if __name__ == '__main__':
    bot.run()
