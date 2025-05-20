import random

# Valeurs en Belote coinchée
TRUMP_VALUES = {'J':20, '9':14, 'A':11, '10':10, 'K':4, 'Q':3, '8':0, '7':0}
NORMAL_VALUES = {'A':11, '10':10, 'K':4, 'Q':3, 'J':2, '9':0, '8':0, '7':0}

SUITS = ['♠', '♥', '♦', '♣']  # on peut aussi utiliser ['S','H','D','C']
RANKS = ['7','8','9','J','Q','K','10','A']

class BeloteGame:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = ['SOUTH','WEST','NORTH','EAST']  # index 0 = vous
        self.hands = {}            # mains: {player: [cards]}
        self.bids = []             # enchères successives
        self.contract = None       # {'player', 'points', 'suit', 'coinched', 'surcoinched'}
        self.current_player = 0    # index du joueur à agir
        self.trick = []            # pli en cours: [(player,card), ...]
        self.won_tricks = {p: [] for p in self.players}
        self.scores = {'NS':0, 'WE':0}
        self.trump = None

    def to_dict(self):
        return {
            'hands': self.hands,
            'bids': self.bids,
            'contract': self.contract,
            'current_player': self.current_player,
            'trick': self.trick,
            'won_tricks': self.won_tricks,
            'scores': self.scores,
            'trump': self.trump
        }

    @classmethod
    def from_dict(cls, room_id, data):
        g = cls(room_id)
        g.hands = data['hands']
        g.bids = data['bids']
        g.contract = data['contract']
        g.current_player = data['current_player']
        g.trick = data['trick']
        g.won_tricks = data['won_tricks']
        g.scores = data['scores']
        g.trump = data['trump']
        return g

    def start_game(self):
        # Prépare le jeu, distribue 8 cartes à chacun
        deck = [r + s for s in SUITS for r in RANKS]
        random.shuffle(deck)
        for i, p in enumerate(self.players):
            self.hands[p] = deck[i*8:(i+1)*8]
        self.current_player = 0  # SOUTH démarre l'enchère

    def bots_make_bids(self):
        """Les 3 bots enchérissent aléatoirement ou passent."""
        last = 0
        suits = SUITS.copy()
        for i in [1,2,3]:
            p = self.players[(self.current_player + i) % 4]
            # probabilité 50% de passer
            if random.random() < 0.5:
                self.bids.append({'player': p, 'bid': 'PASS'})
            else:
                pts = random.choice(range(last+10, 170, 10))
                suit = random.choice(suits)
                last = pts
                self.bids.append({'player': p, 'bid': (pts, suit)})
        # On ne gère ici que la phase initiale, sans coinche

    def process_user_bid(self, pts, suit):
        self.bids.append({'player': self.players[self.current_player], 'bid': (pts, suit)})
        # bots enchérissent ensuite
        self.bots_make_bids()
        # on choisit le plus haut
        valid = [b['bid'] for b in self.bids if b['bid'] != 'PASS']
        if not valid:
            # tout le monde a passé
            self.contract = None
        else:
            pts_max, suit_max = max(valid, key=lambda x: x[0])
            winner = next(b['player'] for b in self.bids if b['bid'] == (pts_max, suit_max))
            self.contract = {
                'player': winner,
                'points': pts_max,
                'suit': suit_max,
                'coinched': False,
                'surcoinched': False
            }
            self.trump = suit_max
        # on passe à la phase de jeu
        return self.contract

    def play_card(self, player, card):
        """Le joueur joue une carte. On continue avec bots + résolution du pli."""
        # retirer de la main
        self.hands[player].remove(card)
        self.trick.append((player, card))
        # bots jouent s’ils sont après
        idx = self.players.index(player)
        for i in [1,2,3]:
            p = self.players[(idx + i) % 4]
            c = self._choose_bot_card(p)
            self.hands[p].remove(c)
            self.trick.append((p, c))
        # déterminer le gagnant du pli
        winner = self._determine_trick_winner()
        self.won_tricks[winner].extend([c for _,c in self.trick])
        self.trick = []
        self.current_player = self.players.index(winner)
        return winner

    def _choose_bot_card(self, player):
        hand = self.hands[player]
        # joue aléatoirement (sans intelligence)
        return random.choice(hand)

    def _determine_trick_winner(self):
        lead_suit = self.trick[0][1][-1]
        best = self.trick[0]
        for ply, card in self.trick[1:]:
            rank, suit = card[:-1], card[-1]
            best_rank, best_suit = best[1][:-1], best[1][-1]
            if suit == self.trump:
                if best_suit != self.trump or TRUMP_VALUES[rank] > TRUMP_VALUES[best_rank]:
                    best = (ply, card)
            elif suit == lead_suit and best_suit != self.trump:
                if NORMAL_VALUES[rank] > NORMAL_VALUES[best_rank]:
                    best = (ply, card)
        return best[0]

    def compute_scores(self):
        """Calcule les points par équipe, version simplifiée."""
        pts_NS = sum(
            NORMAL_VALUES[c[:-1]] if c[-1] != self.trump else TRUMP_VALUES[c[:-1]]
            for p in ['SOUTH','NORTH'] for c in self.won_tricks[p]
        )
        pts_WE = sum(
            NORMAL_VALUES[c[:-1]] if c[-1] != self.trump else TRUMP_VALUES[c[:-1]]
            for p in ['WEST','EAST'] for c in self.won_tricks[p]
        )
        self.scores = {'NS': pts_NS, 'WE': pts_WE}
        return self.scores
