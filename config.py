api_id = 123456
api_hash = 'ffffffffffffffffffffffffffffff'
PHONE = '+10001000000'
session_name = 'session1'

unobot_username = 'unobot'
# should be a int or None
default_delay = None
# print all of the bot's cards
print_cards = True
# if true, the bot will not react to any command-like things
disable_all_commands = False

game_autostart = False
# if game_autostart is True, the following fields are needed
# can also be a link
unogroup_chatname = None
#unogroup_chatname = 'https://t.me/xxxx'

# %username% %firstname% is available
game_consts = {
    'create' : 'Created a new game!|创建新游戏成功！|已經開始咗新一盤!|已開始新的遊戲!|Novo jogo criado!', #en_US, zh_CN, zh_HK, zh_TW, pt_BR
    'end'    : 'Game ended',
    'start'  : 'First player:',
    'win'    : '%firstname% won!',
    'myturn' : '(@%username%)'
}