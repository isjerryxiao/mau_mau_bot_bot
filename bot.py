#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from telethon.sync import TelegramClient
from telethon import events
import re
import logging
import time
import sys
from telethon.tl.functions.messages import GetInlineBotResultsRequest, SendInlineBotResultRequest, SendMessageRequest, SetTypingRequest
from telethon.tl.types import SendMessageTypingAction, SendMessageCancelAction
from telethon.tl.types import PeerUser, PeerChat, PeerChannel, User as _User, Chat as _Chat, Channel as _Channel
from telethon.errors.rpcbaseerrors import RPCError
import asyncio

from game import Game
from card import GREY_SET_ID

game = Game()

from config import api_id, api_hash, PHONE, session_name, unobot_username, default_delay, print_cards, disable_all_commands, game_autostart, unogroup_chatname, game_consts

game.delay = default_delay

SAFE_MODE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = TelegramClient(session_name, api_id, api_hash, sequential_updates=True, use_ipv6=False)
while not client.start(phone=PHONE):
    logger.info("Start failed. Retrying...")
    time.sleep(5)
logger.info("Started!")

my_username = client.get_me().username
my_firstname = client.get_me().first_name

# parse game_consts
for key in game_consts:
    game_consts[key] = game_consts[key].replace('%username%', my_username)
    game_consts[key] = game_consts[key].replace('%firstname%', my_firstname)


def _print(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

logger.info("Getting dialogs")
for dialog in client.iter_dialogs():
    pass
    #_print(dialog)
logger.info("Done getting dialogs")

unobot = client.get_input_entity(unobot_username)
unochat = None
if unogroup_chatname:
    unochat = client.get_input_entity(unogroup_chatname)


async def startgame_task():
    logger.info("startgame_task run")
    if not game.is_playing:
        await client(SendMessageRequest(unochat, "/new@{}".format(unobot_username)))
        await asyncio.sleep(60)
        game.delay = 8
        #try starting the game
        await client(SendMessageRequest(unochat, "/start@{}".format(unobot_username)))
        logger.info("startgame_task game started")

async def task_run():
    import schedule_async as schedule
    """ To start game automatically
    """
    at_times = ("9:00", "12:00", "16:00", "18:00", "19:00", "20:00", "21:30")
    logger.info("Coroutine task_run started")
    for at_time in at_times:
        schedule.every().day.at(at_time).do(startgame_task)
    # for debug only
    #schedule.every(20).seconds.do(testjob)
    while True:
        await schedule.run_pending()
        await asyncio.sleep(60)

async def inline_query(fail=None):
    """ This part handles interaction with unobot.
    """
    # typing @unobot and a space :)
    async def set_typing(cancel=False):
        '''let others see you are typing'''
        if cancel:
            try:
                await client(SetTypingRequest(
                    peer = unochat,
                    action = SendMessageCancelAction()
                ))
            except Exception as err:
                print(err)
        else:
            try:
                await client(SetTypingRequest(
                    peer = unochat,
                    action = SendMessageTypingAction()
                ))
            except Exception as err:
                print(err)
    async def typing_sleep(seconds):
        ''' Telegram cancels your typing notification in several secs
            we also call set_typing in the beginning
        '''
        INTERVAL = 5
        seconds = int(seconds)
        if seconds <= 0:
            pass
        else:
            if seconds <= INTERVAL:
                await asyncio.sleep(INTERVAL)
            else:
                rounds = int(seconds/INTERVAL)
                for i in range(rounds):
                    await asyncio.sleep(INTERVAL)
                    await set_typing()
                assert (seconds - rounds * INTERVAL) > 0
                await asyncio.sleep(int(seconds - rounds * INTERVAL))
    await set_typing()
    for tries in range(10):
        try:
            bot_results = await client(GetInlineBotResultsRequest(
                unobot, unochat, '', ''
            ))
        except RPCError:
            await asyncio.sleep(1)
        else:
            break
    if bot_results.results:
        query_id = bot_results.query_id
        for result in bot_results.results:
            # is it a grey card? if so, get it.
            try:
                if hasattr(result.document.attributes[1], 'stickerset'):
                    try:
                        (result_id, anti_cheat) = result.id.split(':')
                    except:
                        pass
                    else:
                        if len(result_id) == 36:
                            # uuid result for grey cards
                            sset = result.document.attributes[1].stickerset
                            if str(sset.id) == GREY_SET_ID:
                                game.add_grey_card(result.document.id)
                                continue
            except (AttributeError, IndexError):
                pass
            except Exception as err:
                logger.critical('Exception while getting grey cards, {}'.format(str(err)))
            # get ordinary cards
            try:
                (result_id, anti_cheat) = result.id.split(':')
            except ValueError:
                if fail is None:
                    fail = 1
                    await asyncio.sleep(1)
                    await inline_query(fail=fail)
                    return
                elif fail < 5:
                    fail += 1
                    await asyncio.sleep(1)
                    await inline_query(fail=fail)
                    return
                else:
                    return
            game.add_card(result_id, anti_cheat)
        if game.delay:
            await typing_sleep(game.delay)
        if print_cards:
            _print(game.print_cards())
        callback_id = game.play_card()
        if not callback_id:
            callback_id = 'draw'
            await client(SendMessageRequest(unochat, 'Error: No card can be played. Leaving game'))
            await client(SendMessageRequest(unochat, "/leave@{}".format(unobot_username)))
            return
        for tries in range(6):
            try:
                await client(SendInlineBotResultRequest(
                    unochat,
                    query_id,
                    "{}:{}".format(callback_id, game.anti_cheat)
                ))
            except Exception as err:
                logger.critical('Exception: {}'.format(err))
                #await client(SendMessageRequest(unochat, 'Exception: {}'.format(err)))
            else:
                break
        await set_typing(cancel=True)
        game.rotate_deck()
        return True
    else:
        logger.critical('Bad inline result from bot')
        _print(bot_results)
    return None


def safety_check(chat_id, force=False):
    if SAFE_MODE or force:
        safe_ids = [-1001000100100, ]
        if chat_id in safe_ids:
            return True
        else:
            return False
    else:
        return True

def commandify(text, my_commands=True, wild_card=True):
    args = text.split()
    if not args:
        return [None]
    match = re.match(r'/([^@]+$)', args[0])
    if match:
        command = match.group(1)
        if not wild_card:
            return [None]
        username = my_username
        args = args[1:]
        return [command, username, args]
    else:
        match = re.match(r'/([^@]+)@([^@]+)$', args[0])
        if match:
            username = match.group(2)
            command = match.group(1)
            args = args[1:]
            if username != my_username and my_commands == True:
                return [None]
            else:
                return [command, username, args]
        else:
            return [None]

def get_peer_id(peer, reverse=False):
    '''
    reverse = False:
        peer: telethon.tl.types.PeerUser, PeerChat, PeerChannel / User, Chat, Channel
        return int (-100xxxx)
    reverse = True:
        peer: int (-100xxxx)
        return int (xxxx)
    '''
    if reverse:
        str_peer = str(peer)
        if str_peer.startswith("-100"):
            orig_id = str_peer[4:]
            return orig_id
        else:
            return peer
    else:
        peerid = None
        if type(peer) is PeerChannel:
            peerid = getattr(peer, 'channel_id')
            peerid = int('-100{}'.format(peerid))
        elif type(peer) in [ _Channel, _Chat]:
            peerid = getattr(peer, 'id')
            peerid = int('-100{}'.format(peerid))
        elif type(peer) is PeerChat:
            peerid = getattr(peer, 'chat_id')
            peerid = int('-100{}'.format(peerid))
        elif type(peer) is PeerUser:
            peerid = getattr(peer, 'user_id')
        elif type(peer) is _User:
            peerid = getattr(peer, 'id')
        else:
            _print("Error: ", peer)
        if not peerid:
            _print('W: Peer_id is none')
    return peerid


class EmptyChat:
    def __init__(self, title=None):
        self.title = title

class EmptyUser:
    def __init__(self, first_name="None", last_name=None, username=None):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username

def display_username(user, atuser=False, shorten=False):
    if user.first_name and user.last_name:
        name = "{} {}".format(user.first_name, user.last_name)
    else:
        name = user.first_name
    if shorten:
        return name
    if user.username:
        if atuser:
            name += " (@{})".format(user.username)
        else:
            name += " ({})".format(user.username)
    return name


max_items = 10000
cached_ids = list()
cached_entity = list()
# It's a mess, but works
# Welcome to pr
async def mwt_get_entity(entity_type, client, peer, retry=0, from_group=None):
    global max_items, cached_ids, cached_entity
    def get(unique_id):
        global cached_ids, cached_entity
        try:
            my_index = cached_ids.index(unique_id)
            entity = cached_entity[my_index]
            return entity
        except ValueError:
            return None
    def store(unique_id, entity):
        global cached_ids, cached_entity
        cached_ids.append(unique_id)
        cached_entity.append(entity)

    while len(cached_ids) > max_items:
        cached_ids.pop(0)
        cached_entity.pop(0)

    try:
        if entity_type == 'group':
            unique_id = get_peer_id(peer)
            entity = get(unique_id)
            #_print("cache")
            if not entity:
                #_print("new")
                entity = await client.get_entity(peer)
        elif entity_type == 'user':
            unique_id = peer
            entity = get(unique_id)
            #_print("cache")
            if not entity:
                #_print("new")
                entity = await client.get_entity(PeerUser(user_id=peer))
        else:
            return None
        store(unique_id, entity)
        return entity
    except (ValueError, KeyError) as err:
        if retry < 1:
            retry += 1
            if entity_type == 'group':
                sys.stdout.write("[Fetching user from group] Error while getting chat: {}".format(err))
                sys.stdout.flush()
            elif entity_type == 'user':
                sys.stdout.write("[Fetching user from group] Error while getting user: {}".format(err))
                sys.stdout.flush()
                if from_group:
                    for user in await client.get_participants(from_group):
                        unique_id = user.id
                        entity = user
                        if unique_id not in cached_ids:
                            store(unique_id, entity)
            entity = await mwt_get_entity(entity_type, client, peer, retry=retry)
            store(unique_id, entity)
            return entity
        else:
            if entity_type == 'group':
                sys.stdout.write("[Give up] Error while getting chat: {}".format(err))
                sys.stdout.flush()
                entity = EmptyChat(str(id))
            elif entity_type == 'user':
                sys.stdout.write("[Give up] Error while getting user: {}".format(err))
                sys.stdout.flush()
                entity = EmptyUser(first_name="PeerUser(user_id={})".format(peer))
            store(unique_id, entity)
            return entity


async def get_full_info(event):
    '''
        # full_user = client(GetFullUserRequest(id=PeerUser(user_id=msg.from_id)))
        # full_chat = client(GetFullChatRequest(chat_id=chat_id))
        # full_channel = client(GetFullChannelRequest(channel=PeerChannel(channel_id=None)))
        # first_name = full_user.user.first_name
        # last_name = full_user.user.last_name
        # username = full_user.user.username
        # title = full_chat.chats[0].title
        # title = full_channel.chats[0].title
    '''
    orig_user_id = event.message.from_id
    user_id = get_peer_id(PeerUser(user_id=orig_user_id))
    if event.is_channel:
        #channel = client.get_entity(event.message.to_id)
        #user = client.get_entity(PeerUser(user_id=event.message.from_id))
        channel = await mwt_get_entity('group', client, event.message.to_id)
        user = await mwt_get_entity('user', client, event.message.from_id, from_group=event.message.to_id)
        channel_id = get_peer_id(channel)
        full_info = ['Channel', channel, user, channel_id, user_id]
    elif event.is_group:
        group = await mwt_get_entity('group', client, event.message.to_id)
        group_id = get_peer_id(group)
        user = await mwt_get_entity('user', client, event.message.from_id, from_group=event.message.to_id)
        full_info = ['Group', group, user, group_id, user_id]
    elif event.is_private:
        user = await mwt_get_entity('user', client, event.message.from_id)
        full_info = ['User', EmptyChat(), user, user_id, user_id]
    else:
        return None

    return full_info



@client.on(events.NewMessage)
async def new_msg_handler(event):
    global unochat
    #print(event)
    #sys.stdout.flush()
    full_info = await get_full_info(event)
    msg = event.message
    if msg.message and (not msg.media):
        # Text handler
        logger.info("{} - {} - {}: {}".format(full_info[0], full_info[1].title, display_username(full_info[2]), msg.message))
        if not safety_check(get_peer_id(msg.to_id)):
            return
        # react to commands
        if not disable_all_commands:
            c = commandify(event.raw_text, wild_card=False)
            if c[0]:
                if c[0] == 'hello':
                    await event.reply('hi!')
                if c[0] in ['startgame', 'start', 'join'] and full_info[0] == "Channel":
                    if game.is_playing:
                        await event.reply("I'm playing right now.")
                    else:
                        unochat = msg.to_id
                        game.join_game(get_peer_id(unochat))
                        await client(SendMessageRequest(unochat, "/join@{}".format(unobot_username)))
                elif c[0] in ['stopgame', 'stop', 'leave'] and full_info[0] == "Channel":
                    if game.is_playing:
                        game.leave_game(get_peer_id(unochat))
                        game.stop_game()
                        await client(SendMessageRequest(unochat, "/leave@{}".format(unobot_username)))
                    elif game.joined and get_peer_id(unochat) in game.joined:
                        game.leave_game(get_peer_id(unochat))
                        await client(SendMessageRequest(unochat, "/leave@{}".format(unobot_username)))
                    else:
                        await event.reply("I'm not playing right now.")
                elif c[0] in ['wait', 'delay'] and full_info[0] == "Channel":
                    if game.delay or (not game.is_playing):
                        await event.reply("Nothing to do.")
                    else:
                        game.delay = 8
                        await event.reply("OK. {} seconds of delay has been set.".format(game.delay))
                elif c[0] in ['nowait', 'nodelay'] and full_info[0] == "Channel":
                    if game.delay and game.is_playing:
                        myreply = "OK. {} seconds of delay has been removed.".format(game.delay)
                        game.delay = None
                        await event.reply(myreply)
                    else:
                        await event.reply("Nothing to do.")
                return
        # react to unobot
        if full_info[2].username and full_info[2].username == unobot_username:
            if re.search(game_consts['myturn'], msg.message):
                if re.search(game_consts['start'], msg.message):
                    # I'm the first player
                    if not game.is_playing:
                        unochat = msg.to_id
                        if game.joined and get_peer_id(unochat) in game.joined:
                            logger.info('Bot: Game started. I\'m the first player.')
                            game.start_game()
                logger.info('Bot: It\'s my turn.')
                if game.joined and get_peer_id(unochat) in game.joined:
                    if not game.is_playing:
                        logger.info('Bot: Game started a long time ago. I joined midway.')
                        game.start_game()
                    await inline_query()
                else:
                    logger.info('I\'m not playing in {} - {}'.format(full_info[1].title, get_peer_id(unochat)))
                    await client(SendMessageRequest(unochat, "/leave@{}".format(unobot_username)))
            elif re.search(game_consts['end'], msg.message):
                if game.is_playing:
                    logger.info('Bot: Game ended.')
                    game.clear_deck()
                    game.leave_game(get_peer_id(unochat))
                    game.stop_game()
                    game.delay = default_delay
            elif re.search(game_consts['create'], msg.message):
                if not game.is_playing:
                    logger.info('Bot: New game created.')
                    if default_delay:
                        await asyncio.sleep(default_delay)
                    unochat = msg.to_id
                    game.join_game(get_peer_id(unochat))
                    await client(SendMessageRequest(unochat, "/join@{}".format(unobot_username)))
            elif re.search(game_consts['start'], msg.message):
                if not game.is_playing:
                    unochat = msg.to_id
                    if game.joined and get_peer_id(unochat) in game.joined:
                        logger.info('Bot: Game started.')
                        game.start_game()
                    else:
                        await client(SendMessageRequest(unochat, "/leave@{}".format(unobot_username)))
            elif re.search(game_consts['win'], msg.message):
                if game.is_playing:
                    logger.info('Bot: I win.')
                    game.clear_deck()
                    game.leave_game(get_peer_id(unochat))
                    game.stop_game()

    elif msg.media:
        # Has media, interesting.
        media = msg.media
        type = None
        if hasattr(media, 'photo'):
            type = "photo"
            logger.info("{} - {} - {}: [Photo]".format(full_info[0], full_info[1].title, display_username(full_info[2])))
        elif hasattr(media, 'document'):
            try:
                if hasattr(media.document.attributes[1], 'stickerset'):
                    type = "Sticker"
                    logger.info("{} - {} - {}: [Sticker]:{}".format(full_info[0], full_info[1].title, display_username(full_info[2]), media.document.attributes[1].alt))
                else:
                    type = "Document (file)"
                    logger.info("{} - {} - {}: [Document (file)]".format(full_info[0], full_info[1].title, display_username(full_info[2])))
            except (AttributeError, IndexError):
                type = "Document"
                logger.info("{} - {} - {}: [Document]".format(full_info[0], full_info[1].title, display_username(full_info[2])))
        else:
            type = "Unknown media"
            logger.info("{} - {} - {}: [Unknown media]".format(full_info[0], full_info[1].title, display_username(full_info[2])))
        logger.debug("Media Type: {}".format(type))
    # Handler complete


# for debug only
async def testjob():
    print('aaa')


async def main():
    # requires python 3.7 +
    #if game_autostart:
        #asyncio.create_task(task_run())
    await client.run_until_disconnected()
    #await client.disconnected

loop = asyncio.get_event_loop()
# this can run on python 3.5
if game_autostart:
    loop.create_task(task_run())
try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    client.disconnect()
