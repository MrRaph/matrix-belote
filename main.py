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
    if not m.command('start'):
        return

    key = room.room_id
    human = message.sender
    bots = [f"Bot{i}" for i in range(1, 4)]
    players = [human] + bots

    game = BeloteGame(key, players)
    game.start()
    st[key] = game.to_dict()

    # Affichage de la table
    table_txt = (
        "Table :\n"
        f"   Nord : {players[2]}\n"
        f"Ouest : {players[1]}    Est : {players[3]}\n"
        f"   Sud : {players[0]} (vous)\n"
        f"Partenaire : {players[2]}"
    )
    await bot.api.send_text_message(room.room_id, table_txt)

    # Affichage de la main
    hand = ' '.join(sorted(game.hands[human]))
    await bot.api.send_text_message(room.room_id, f"Votre main : {hand}")

    # Déclenche enchères bots
    await process_bots_auction(room.room_id, human, game, st)

async def process_bots_auction(room_id, human, game, st):
    auction = game.auction
    msgs = []
    while not auction.finished and auction.players[auction.current] != human:
        p = auction.players[auction.current]
        if auction.best is None:
            action = random.choice(['pass','bid'])
        else:
            action = 'pass' if auction.best['points']>=160 else random.choice(['pass','pass','bid'])
        if action=='pass':
            auction.propose(p,'pass')
            msgs.append(f"{p} a PASSÉ.")
        else:
            min_pts = auction.best['points']+10 if auction.best else 80
            options = [v for v in range(min_pts,161,10)]
            if not options:
                auction.propose(p,'pass')
                msgs.append(f"{p} a PASSÉ.")
            else:
                pts = random.choice(options)
                suit = random.choice(['♠','♥','♦','♣','SA','TA'])
                try:
                    auction.propose(p,'bid',pts,suit)
                    msgs.append(f"{p} a ENCHÉRI : {pts}{suit}.")
                except ValueError:
                    auction.propose(p,'pass')
                    msgs.append(f"{p} a PASSÉ.")
        st[room_id]=game.to_dict()
    # Publier\    
    text = f"Enchères :\n{auction.summary()}"
    for m in msgs: text+=f"\n{m}"
    if auction.finished:
        if auction.best:
            b=auction.best
            text+=f"\nContrat -> {b['points']}{b['suit']} par {b['player']}"
        else:
            text+="\nTout le monde a passé !"
        text+=f"\nPhase de jeu : {game.players[game.turn_idx]} commence."
    else:
        text+="\nÀ vous de PARLER."
    await bot.api.send_text_message(room_id,text)
    st[room_id]=game.to_dict()

@bot.listener.on_message_event
@state.ensure_state
async def on_auction(room, message, st):
    m=match(room,message)
    if not m.command():return
    key=room.room_id
    game=BeloteGame.from_dict(key,st[key])
    if game.phase!='auction':return
    user=message.sender
    cmd=m.command()
    try:
        if cmd=='pass': res=game.process_auction(user,'pass')
        elif cmd=='bid': args=m.args();res=game.process_auction(user,'bid',int(args[0]),args[1])
        elif cmd=='coinche':res=game.process_auction(user,'coinche')
        elif cmd=='surcoinche':res=game.process_auction(user,'surcoinche')
        else: return
    except Exception as e:
        await bot.api.send_text_message(key,f"Erreur enchère: {e}");return
    st[key]=game.to_dict()
    await process_bots_auction(key, user, game, st)
    # Phase de jeu : simulation automatique des bots après enchères
    if game.phase == 'play':
        # tant que ce n'est pas le tour humain
        while game.phase == 'play' and game.players[game.turn_idx] != user:
            bot_p = game.players[game.turn_idx]
            played = None
            winner = None
            # choisir première carte légale
            for card in list(game.hands[bot_p]):
                try:
                    winner = game.play_card(bot_p, card)
                    played = card
                    break
                except ValueError:
                    continue
            if not played:
                break
            # sauvegarder et annoncer
            st[key] = game.to_dict()
            await bot.api.send_text_message(key, f"{bot_p} joue {played}")
            if winner:
                await bot.api.send_text_message(key, f"Pli remporté par {winner}")
        # retour au joueur humain
        if game.phase == 'play':
            await bot.api.send_text_message(key, "À vous de jouer.")
        st[key] = game.to_dict()

@bot.listener.on_message_event
@state.ensure_state
async def show_hand(room,message,st):
    m=match(room,message)
    if not m.command('hand'):return
    key=room.room_id
    game=BeloteGame.from_dict(key,st.get(key,{}))
    hand=game.hands.get(message.sender,[])
    await bot.api.send_text_message(key,f"Votre main : {' '.join(sorted(hand))}")

if __name__=='__main__':
    bot.run()