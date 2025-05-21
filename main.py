import os
import random
import simplematrixbotlib as botlib
from belote import BeloteGame
import state

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
@state.ensure_state
async def on_start(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command('start'):
        return
    key = room.room_id
    human = message.sender
    bots = [f"Bot{i}" for i in range(1,4)]
    players = [human] + bots
    game = BeloteGame(key, players)
    game.start()
    st[key] = game.to_dict()
    # Affichage table
    txt = (
        "Table:\n"
        f"   Nord: {players[2]}\n"
        f"Ouest: {players[1]}    Est: {players[3]}\n"
        f"   Sud: {players[0]} (vous)\n"
        f"Partenaire: {players[2]}"
    )
    await bot.api.send_text_message(key, txt)
    # Main humain
    hand = ' '.join(sorted(game.hands[human]))
    await bot.api.send_text_message(key, f"Votre main: {hand}")
    # Lancement enchères
    await process_bots_auction(key, human, game, st)

async def process_bots_auction(room_id, human, game, st):
    auction = game.auction
    msgs = []

    # --- Enchères automatiques des bots jusqu'au joueur humain ---
    while not auction.finished and auction.players[auction.current] != human:
        p = auction.players[auction.current]
        if auction.best is None:
            action = random.choice(['pass', 'bid'])
        else:
            action = 'pass' if auction.best['points'] >= 160 else random.choice(['pass','pass','bid'])
        if action == 'pass':
            auction.propose(p, 'pass')
            msgs.append(f"{p} a PASSÉ.")
        else:
            min_pts = auction.best['points'] + 10 if auction.best else 80
            opts = [v for v in range(min_pts, 161, 10)]
            if not opts:
                auction.propose(p, 'pass')
                msgs.append(f"{p} a PASSÉ.")
            else:
                pts = random.choice(opts)
                suit = random.choice(['♠','♥','♦','♣','SA','TA'])
                try:
                    auction.propose(p, 'bid', pts, suit)
                    msgs.append(f"{p} a ENCHÉRI : {pts}{suit}.")
                except ValueError:
                    auction.propose(p, 'pass')
                    msgs.append(f"{p} a PASSÉ.")
        st[room_id] = game.to_dict()

    # --- Si enchères terminées sans contrat (tout le monde a passé) ---
    if auction.finished and auction.best is None:
        await bot.api.send_text_message(room_id, "Tout le monde a passé ! Nouvelle donne en cours…")
        game.start()
        st[room_id] = game.to_dict()
        # Réafficher la table et la main puis relancer les enchères
        # (reprise du code de on_start)
        players = game.players
        table_txt = (
            f"Table:\n"
            f"   Nord: {players[2]}\n"
            f"Ouest: {players[1]}    Est: {players[3]}\n"
            f"   Sud: {players[0]} (vous)\n"
            f"Partenaire: {players[2]}"
        )
        await bot.api.send_text_message(room_id, table_txt)
        hand = ' '.join(sorted(game.hands[human]))
        await bot.api.send_text_message(room_id, f"Votre main: {hand}")
        return await process_bots_auction(room_id, human, game, st)

    # --- Envoi du résumé des enchères ---
    summary = auction.summary()
    text = f"Enchères:\n{summary}"
    for m in msgs:
        text += f"\n{m}"
    if auction.finished:
        if auction.best:
            b = auction.best
            text += f"\nContrat -> {b['points']}{b['suit']} par {b['player']}"
        else:
            text += "\nTout le monde a passé!"  # ne devrait pas arriver grâce au bloc précédent
        text += f"\nPhase de jeu : {game.players[game.turn_idx]} commence."
    else:
        text += "\nÀ vous de PARLER."

    await bot.api.send_text_message(room_id, text)
    st[room_id] = game.to_dict()

    # --- Dès que la phase passe en 'play', on lance les bots ---
    if game.phase == 'play':
        await process_bots_play(room_id, human, game, st)


async def process_bots_play(room_id, human, game, st):
    # tant que ce n'est pas au joueur humain
    while game.phase == 'play' and game.players[game.turn_idx] != human:
        p = game.players[game.turn_idx]
        played = None; winner = None
        for c in list(game.hands[p]):
            try:
                winner = game.play_card(p, c)
                played = c
                break
            except ValueError:
                continue
        if not played:
            break
        st[room_id] = game.to_dict()
        await bot.api.send_text_message(room_id, f"{p} joue {played}")
        if winner:
            await bot.api.send_text_message(room_id, f"Pli remporté par {winner}")
    # à vous de jouer
    if game.phase == 'play':
        await bot.api.send_text_message(room_id, "À vous de jouer.")
        st[room_id] = game.to_dict()

@bot.listener.on_message_event
@state.ensure_state
async def on_auction(room, message, st):
    m = match(room, message)
    if not m.prefix(): return
    key = room.room_id
    game = BeloteGame.from_dict(key, st[key])
    if game.phase != 'auction': return
    user = message.sender
    try:
        if m.command('pass'):
            game.process_auction(user, 'pass')
        elif m.command('bid'):
            a = m.args(); game.process_auction(user, 'bid', int(a[0]), a[1])
        else: return
    except Exception as e:
        await bot.api.send_text_message(key, f"Erreur enchère: {e}"); return
    st[key] = game.to_dict()
    await process_bots_auction(key, user, game, st)

@bot.listener.on_message_event
@state.ensure_state
async def show_hand(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command('hand'): return
    key = room.room_id
    game = BeloteGame.from_dict(key, st.get(key, {}))
    hand = ' '.join(sorted(game.hands.get(message.sender, [])))
    await bot.api.send_text_message(key, f"Votre main: {hand}")

# gestion du coup du joueur humain
@bot.listener.on_message_event
@state.ensure_state
async def on_play(room, message, st):
    m = match(room, message)
    if not m.prefix() or not m.command('play'): return
    key = room.room_id
    game = BeloteGame.from_dict(key, st.get(key, {}))
    if game.phase != 'play':
        await bot.api.send_text_message(key, "La partie n'est pas en phase de jeu.")
        return
    player = message.sender
    args = m.args()
    if not args:
        await bot.api.send_text_message(key, "Spécifiez une carte, ex: b!play 10♠")
        return
    card = args[0]
    try:
        winner = game.play_card(player, card)
    except Exception as e:
        await bot.api.send_text_message(key, f"Erreur de jeu: {e}")
        return
    st[key] = game.to_dict()
    # annonce du coup joué
    await bot.api.send_text_message(key, f"Vous jouez {card}")
    # si pli terminé
    if winner:
        await bot.api.send_text_message(key, f"Pli remporté par {winner}")
    # bots jouent ensuite
    await process_bots_play(key, player, game, st)

if __name__ == '__main__':
    bot.run()
