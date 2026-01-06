# Server/game.py

import random
from Formats.cards import SUITS, RANK_VALUE_MAP
from Formats.packet_formats import (
    ROUND_ONGOING,
    ROUND_WIN,
    ROUND_LOSS,
    ROUND_TIE,
    HIT,
    STAND,
)

class Deck:
    def __init__(self):
        self.cards = [] # [(rank, suit),..]
        self._build_deck()
        self.shuffle()

    def _build_deck(self):
        """
        Create a standard 52-card deck.
        Each card is represented as (rank, suit)
        """
        self.cards = []
        for suit in SUITS.keys():      # 0..3
            for rank in range(1, 14):  # 1..13
                self.cards.append((rank, suit))

    def shuffle(self):
        random.shuffle(self.cards)

    def draw_card(self):
        """
        Draw one card from the deck.
        Raises error if deck is empty.
        """
        if not self.cards:
            raise RuntimeError("Deck is empty")
        return self.cards.pop()

class Hand:
    def __init__(self):
        self.cards = []

    def add_card(self, card):
        """
        card is a tuple: (rank, suit)
        """
        self.cards.append(card)

    def get_value(self) -> int:
        """
        Calculate total value of the hand.
        """
        total = 0
        for rank, _ in self.cards:
            total += RANK_VALUE_MAP[rank]
        return total

    def is_bust(self) -> bool:
        return self.get_value() > 21

class BlackjackGame:
    def __init__(self):
        self.deck = None
        self.player = Hand()
        self.dealer = Hand()
        self.round_over = False

    def start_round(self):
        """
        Start a new round: fresh deck, clear hands, initial deal.
        Returns: (result, card)
        card is the last dealt card to the PLAYER (rank, suit) or None
        """
        self.deck = Deck()
        self.player = Hand()
        self.dealer = Hand()
        self.round_over = False

        # Initial deal (example: player gets 2, dealer gets 2)
        # We'll decide what to return to client in server.py,
        # but here we just perform the deal.
        p1 = self.deck.draw_card()
        p2 = self.deck.draw_card()
        d1 = self.deck.draw_card()
        d2 = self.deck.draw_card()

        self.player.add_card(p1)
        self.player.add_card(p2)
        self.dealer.add_card(d1)
        self.dealer.add_card(d2)

        return ROUND_ONGOING, None

    def player_hit(self):
        """
        Player takes a card.
        Returns: (result, card_drawn)
        """
        if self.round_over:
            raise RuntimeError("Round already finished")

        card = self.deck.draw_card()
        self.player.add_card(card)

        if self.player.is_bust(): # if the player busts (>21).
            self.round_over = True
            return ROUND_LOSS, card

        return ROUND_ONGOING, card

    def player_stand(self):
        """
        Player stands; dealer draws until >= 17; decide winner.
        Returns:
            (final_result, dealer_drawn_cards)
        dealer_drawn_cards is a list of (rank, suit) drawn by dealer during this stand.
        """
        if self.round_over:
            raise RuntimeError("Round already finished")

        dealer_drawn = []
        while self.dealer.get_value() < 17:
            card = self.deck.draw_card()
            self.dealer.add_card(card)
            dealer_drawn.append(card)

        self.round_over = True

        if self.dealer.is_bust():
            return ROUND_WIN, dealer_drawn

        p = self.player.get_value()
        d = self.dealer.get_value()

        if p > d:
            return ROUND_WIN, dealer_drawn
        if p < d:
            return ROUND_LOSS, dealer_drawn
        return ROUND_TIE, dealer_drawn
