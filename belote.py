import random

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['7', '8', '9', 'J', 'Q', 'K', '10', 'A']

TRUMP_VALUES = {'J': 20, '9': 14, 'A': 11, '10': 10, 'K': 4, 'Q': 3, '8': 0, '7': 0}
NORMAL_VALUES = {'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0, '8': 0, '7': 0}
SA_VALUES = NORMAL_VALUES.copy()
SA_VALUES['A'] = 19

class Auction:
    """Gestion des enchères"""
    def __init__(self, players):
        self.players = list(players)
        self.current = 0
        self.bids = []
        self.best = None
        self.pass_count = 0
        self.coinched_by = None
        self.surcoinched_by = None
        self.finished = False

    def propose(self, player, action, points=None, suit=None):
        if self.finished:
            raise ValueError("Enchères déjà terminées")
        if self.players[self.current] != player:
            raise ValueError("Pas votre tour")
        if action == 'pass':
            self.bids.append({'player': player, 'type': 'pass'})
            self.pass_count += 1
        elif action == 'bid':
            if suit not in SUITS + ['SA', 'TA'] or points % 10 != 0 or not (80 <= points <= 160):
                raise ValueError("Enchère invalide")
            if self.best and points <= self.best['points']:
                raise ValueError("Surenchère nécessaire")
            self.best = {'player': player, 'points': points, 'suit': suit}
            self.bids.append({'player': player, 'type': 'bid', 'points': points, 'suit': suit})
            self.pass_count = 0
        elif action == 'coinche':
            if not self.best or self.best['player'] == player or self.coinched_by:
                raise ValueError("Impossible de coincher")
            self.coinched_by = player
            self.finished = True
            return
        elif action == 'surcoinche':
            if not self.coinched_by or self.best['player'] == player or self.surcoinched_by:
                raise ValueError("Impossible de surcoincher")
            self.surcoinched_by = player
            self.finished = True
            return
        else:
            raise ValueError("Action inconnue")
        self.current = (self.current + 1) % len(self.players)
        if self.pass_count >= len(self.players) - 1 and self.best:
            self.finished = True

    def summary(self):
        lines = []
        for b in self.bids:
            if b['type'] == 'pass':
                lines.append(f"- {b['player']}: PASS")
            else:
                lines.append(f"- {b['player']}: {b['points']}{b['suit']}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            'players': self.players,
            'current': self.current,
            'bids': self.bids,
            'best': (self.best['player'], self.best['points'], self.best['suit']) if self.best else None,
            'pass_count': self.pass_count,
            'coinched_by': self.coinched_by,
            'surcoinched_by': self.surcoinched_by,
            'finished': self.finished
        }

    @classmethod
    def from_dict(cls, data):
        a = cls(data['players'])
        a.current = data['current']
        a.bids = data['bids']
        if data['best']:
            pl, pts, st = data['best']
            a.best = {'player': pl, 'points': pts, 'suit': st}
        a.pass_count = data['pass_count']
        a.coinched_by = data['coinched_by']
        a.surcoinched_by = data['surcoinched_by']
        a.finished = data['finished']
        return a

class BeloteGame:
    def __init__(self, room_id, players):
        self.room_id = room_id
        self.players = list(players)
        self.dealer_idx = -1
        self.auction = None
        self.hands = {p: [] for p in self.players}
        self.trump = None
        self.phase = None
        self.turn_idx = None
        self.trick = []
        self.won = {p: [] for p in self.players}
        self.scores = {}
        self.preneur = None
        self.contract = None
        self.last_trick_winner = None

    def rotate_dealer(self):
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
        self.turn_idx = (self.dealer_idx + 1) % len(self.players)

    def deal(self):
        deck = [r + s for s in SUITS for r in RANKS]
        random.shuffle(deck)
        for i, p in enumerate(self.players):
            self.hands[p] = deck[i*8:(i+1)*8]

    def start(self):
        self.rotate_dealer()
        self.deal()
        self.auction = Auction(self.players)
        self.phase = 'auction'

    def to_dict(self):
        return {
            'players': self.players,
            'dealer_idx': self.dealer_idx,
            'hands': self.hands,
            'trump': self.trump,
            'phase': self.phase,
            'turn_idx': self.turn_idx,
            'trick': self.trick,
            'won': self.won,
            'scores': self.scores,
            'preneur': self.preneur,
            'contract': self.contract,
            'last_trick_winner': self.last_trick_winner,
            'auction': self.auction.to_dict()
        }

    @classmethod
    def from_dict(cls, room_id, data):
        g = cls(room_id, data['players'])
        g.dealer_idx = data['dealer_idx']
        g.hands = data['hands']
        g.trump = data['trump']
        g.phase = data['phase']
        g.turn_idx = data['turn_idx']
        g.trick = data['trick']
        g.won = data['won']
        g.scores = data['scores']
        g.preneur = data['preneur']
        g.contract = data['contract']
        g.last_trick_winner = data['last_trick_winner']
        g.auction = Auction.from_dict(data['auction'])
        return g

    def process_auction(self, player, action, points=None, suit=None):
        res = self.auction.propose(player, action, points, suit)
        if self.auction.finished:
            if not self.auction.best:
                return 'redeal'
            self.phase = 'play'
            self.preneur = self.auction.best['player']
            self.contract = self.auction.best.copy()
            self.trump = self.contract['suit']
        return res

    def play_card(self, player, card):
        if self.phase != 'play':
            raise ValueError("Pas en phase jeu")
        if self.players[self.turn_idx] != player:
            raise ValueError("Pas votre tour")
        if card not in self.hands[player]:
            raise ValueError("Carte invalide")
        self._enforce_play_rule(player, card)
        self.hands[player].remove(card)
        self.trick.append((player, card))
        self.turn_idx = (self.turn_idx + 1) % len(self.players)
        if len(self.trick) == len(self.players):
            winner = self._determine_trick_winner()
            self.last_trick_winner = winner
            self.won[winner].extend([c for _, c in self.trick])
            self.trick = []
            self.turn_idx = self.players.index(winner)
            if all(len(self.hands[p]) == 0 for p in self.players):
                self.phase = 'done'
            return winner
        return None

    def _enforce_play_rule(self, player, card):
        hand = self.hands[player]
        if self.trick:
            lead_suit = self.trick[0][1][-1]
            if any(c[-1] == lead_suit for c in hand) and card[-1] != lead_suit:
                raise ValueError("Vous devez fournir")
            if not any(c[-1] == lead_suit for c in hand):
                partner = self.players[(self.players.index(player)+2)%4]
                curr = self._determine_trick_winner()
                if any(c[-1] == self.trump for c in hand) and card[-1] != self.trump and curr != partner:
                    raise ValueError("Vous devez couper")
            if card[-1] == self.trump:
                trump_cards = [c for _, c in self.trick if c[-1] == self.trump]
                if trump_cards:
                    best_trump = max(trump_cards, key=lambda x: TRUMP_VALUES[x[:-1]])
                    best_rank = best_trump[:-1]
                    higher = [c for c in hand if c[-1]==self.trump and TRUMP_VALUES[c[:-1]]>TRUMP_VALUES[best_rank]]
                    if TRUMP_VALUES[card[:-1]] < TRUMP_VALUES[best_rank] and higher:
                        raise ValueError("Vous devez surcouper")

    def _determine_trick_winner(self):
        lead = self.trick[0][1][-1]
        best = self.trick[0]
        for ply, card in self.trick[1:]:
            rank, suit = card[:-1], card[-1]
            brank, bsuit = best[1][:-1], best[1][-1]
            if suit == self.trump:
                if bsuit != self.trump or TRUMP_VALUES[rank] > TRUMP_VALUES[brank]:
                    best = (ply, card)
            elif suit == lead and bsuit != self.trump:
                if NORMAL_VALUES[rank] > NORMAL_VALUES[brank]:
                    best = (ply, card)
        return best[0]
