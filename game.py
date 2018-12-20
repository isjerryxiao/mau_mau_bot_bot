#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from card import COLORS, SPECIALS
from card import RED, BLUE, GREEN, YELLOW
from card import GREY_ID
from random import choice, random
import logging

logger = logging.getLogger('card')

def color_from_str(string):
    """Decodes a Card object from a string"""
    # Actuall it should't be "in special"
    if string not in SPECIALS:
        color, value = string.split('_')
        del value
        return color

def cards_sum(deck):
    """How many cards do we have in each color?"""
    # r, b, g, y
    card_count = {RED: 0, BLUE: 0, GREEN: 0, YELLOW: 0}
    for card in deck:
        card_count[color_from_str(card)] += 1
    return card_count

def color_choice(deck, greydeck):
    """Now that we are doing a color choice, which color should we choose?"""
    full_deck = deck + greydeck
    sum = cards_sum(full_deck)
    chosen_color = None
    chosen_number = 0
    for color in (RED, BLUE, GREEN, YELLOW):
        if chosen_number <= sum[color]:
            chosen_number = sum[color]
            chosen_color = color
    if chosen_number == 0 or chosen_color is None:
        chosen_color = choice((RED, BLUE, GREEN, YELLOW))
    return chosen_color

def randchance(chance=0.5):
    """ make simple random choice
        chance can be any number between 0,1
    """
    if chance > random():
        return True
    else:
        return False

class Game():
    def __init__(self):
        self.deck = list()
        self.greydeck = list()
        self.old_deck = list()
        self.old_greydeck = list()
        self.special = list()
        self.functional = list()
        # functional = draw, call_bluff, pass
        # call_bluff > draw
        self.choose_color = list()
        self.joined = None #may be None or a a list of group entity
        self.is_playing = False
        self.anti_cheat = ''
        self.delay = None
    def join_game(self, group):
        if self.joined is None:
            self.joined = list()
        if group in self.joined:
            return True
        self.joined.append(group)
    def leave_game(self, group):
        try:
            if self.joined:
                self.joined.remove(group)
        except ValueError:
            returnValue = False
        else:
            returnValue = True
        if (self.joined is not None) and (not self.joined):
            self.joined = None
        return returnValue
    def start_game(self):
        self.is_playing = True
    def stop_game(self):
        self.is_playing = False
        # delay is set in bot.py
        #self.delay = None
    def rotate_deck(self):
        """Memorize deck for for 1 round in case of color choose"""
        if len(self.choose_color):
            # when choosing color, the bot cannot get any ordinary card. (deck and greydeck are all empty)
            if len(self.deck) != 0 or len(self.greydeck) != 0:
                logger.critical('Unexpected behavior: there\'s cards in deck while choosing color.')
        else:
            self.old_deck = self.deck
            self.old_greydeck = self.greydeck
        self.clear_deck(rotate=True)
    def clear_deck(self, rotate=False):
        if not rotate:
            self.old_deck = list()
            self.old_greydeck = list()
        self.deck = list()
        self.greydeck = list()
        self.special = list()
        self.functional = list()
        self.choose_color = list()
        self.anti_cheat = ''
    def print_cards(self):
        """ print all of my cards
            returns a string that is printable
            note that currently the bot just ignores unplayable special cards
        """
        if len(self.choose_color):
            return str(self.choose_color + self.old_deck + ["[u]" + s for s in self.old_greydeck] + self.special + self.functional)
        else:
            return str(self.deck + ["[u]" + s for s in self.greydeck] + self.special + self.functional)
    def add_grey_card(self, card_id):
        """get grey_cards from id, and add them"""
        grey_card = GREY_ID.get(str(card_id), None)
        if grey_card:
            self.greydeck.append(grey_card)
        else:
            logger.info('Can\'t get any card from the given id {}'.format(card_id))
    def add_card(self, result_id, anti_cheat):
        """add card to deck, refer to the code of unobot for more info"""
        self.anti_cheat = anti_cheat
        if result_id in ('hand', 'gameinfo', 'nogame'):
            return
        elif result_id.startswith('mode_'):
            return
        elif len(result_id) == 36:
            return
        elif result_id == 'call_bluff':
            self.functional.append(result_id)
        elif result_id == 'draw':
            self.functional.append(result_id)
        elif result_id == 'pass':
            self.functional.append(result_id)
        elif result_id in COLORS:
            self.choose_color.append(result_id)
        elif result_id in SPECIALS:
            self.special.append(result_id)
        else:
            self.deck.append(result_id)
    def play_card(self):
        ''' The bot plays its card.
            The deck is refreshed every round,
            currently the bot is unable to know its previously played cards.
        '''
        # in case we are choosing color
        if len(self.choose_color):
            return color_choice(self.old_deck, self.old_greydeck)
        # play ordinary cards
        # and always take special cards into account
        elif len(self.deck):
            if len(self.special) and randchance(0.1):
                return choice(self.special)
            else:
                return choice(self.deck)
        # if we don't have any ordinary cards to play
        # maybe there's a plus four?
        elif len(self.special):
            return choice(self.special)
        elif len(self.functional):
            # or maybe there's a pass?
            if 'pass' in self.functional:
                return 'pass'
            # still no? call his bluff!
            else:
                if 'call_bluff' in self.functional and randchance(0.4):
                    return 'call_bluff'
                # what is left? probably draw(
                else:
                    return choice(self.functional)
