#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Jochens Telegram-OH-Bot
"""

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
                          ConversationHandler, BaseFilter)
from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)
import configparser
import xml.etree.ElementTree as ET
from functools import wraps
import logging
from openhab import openHAB
import requests
from datetime import datetime

# Enable logging
log_output = 2 # 1: use logging module | 2: only print defined output to stdout | 3: no logging or printing
if log_output == 1:
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    logger = logging.getLogger(__name__)

def my_log(logtext):
    global log_output
    if log_output == 1:
        logger.info(logtext)
    if log_output == 2:
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S') + logtext)
        
# Config
config = configparser.ConfigParser()
config.read('bot.ini')
allowed_users = [int(config['USER1']['id']),int(config['USER2']['id'])]
google_maps_api_key = config['KEYS']['maps_api']
coord_home = config['PLACES']['home']
coord_work1 = config['PLACES']['work1']
url_oh = config['URLS']['oh_url']
bot_name = config['BOT']['name']
user1_name = config['USER1']['name']
user2_name = config['USER2']['name']
print('allowed user ids: ' + str(allowed_users))

# Read xml data
xml_tree = ET.parse('bot.xml')
xml_root = xml_tree.getroot()
ThreeSteps_Keywords = []
for elem in xml_root.find('ThreeSteps'):
    ThreeSteps_Keywords.append(elem.tag)
TwoSteps_Keywords = []
for elem in xml_root.find('TwoSteps'):
    TwoSteps_Keywords.append(elem.tag)

def initialize_vars():
    global Keyword
    Keyword = ""
    global Values_1
    Values_1 = []
    global StepOne
    StepOne = ""
    global Values_2
    Values_2 = []
    global StepTwo
    StepTwo = ""
    global Values_3
    Values_3 = []
    global StepThree
    StepThree = ""

def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        if user_id not in allowed_users:
            my_log("access denied to user id %d, %s", user_id, user_name)
            return
        return func(bot, update, *args, **kwargs)
    return wrapped

def build_menu(values,n_cols):
    while len(values) < 5*n_cols:
        values.append(" ")
    button_list = [KeyboardButton(s) for s in values]
    menu = [button_list[i:i + n_cols] for i in range(0, len(button_list), n_cols)]
    return menu

def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def cleanup(value):
    value = value.replace(" %","")
    value = value.replace("%","")
    value = value.replace(" °C","")
    value = value.replace("°C","")
    if (value == "An") or (value == "AN"):
        value = "ON"
    if (value == "Aus") or (value == "AUS"):
        value = "OFF"
    return value

def send_oh(item, value):
    value = cleanup(value)
    try: # an error should not lead to a stop of the script
#        print(item + ": " + str(value))
        if isfloat(value):
            Items.get(item).command(float(value))
        else:
            Items.get(item).command(value)
        return True
    except Exception as e:
        my_log("Error sending to openHAB: %s", e)
        return False

def get_oh(item):
    try:
        return Items.get(item).state
    except Exception as e:
        my_log("Error loading from openHAB: %s", e)
        return "Fehler, sorry..."

def maps_driving_time(orig,dest):
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json?origins={0}&destinations={1}&mode=driving&language=de-DE&departure_time=now&key={2}".format(orig,dest,google_maps_api_key)
        response = requests.get(url)
        result = response.json()
        driving_time = result['rows'][0]['elements'][0]['duration_in_traffic']['value']
        return (driving_time // 60)
    except Exception as e:
        my_log("Error loading Maps Driving Time: %s", e)
        return "(?)"

class Filter3Keywords(BaseFilter):
    def filter(self, message):
        return message.text in ThreeSteps_Keywords
filter_3_keywords = Filter3Keywords()

class Filter31(BaseFilter):
    def filter(self, message):
        return message.text in Values_1
filter_3_1 = Filter31()

class Filter32(BaseFilter):
    def filter(self, message):
        return message.text in Values_2
filter_3_2 = Filter32()

class Filter33(BaseFilter):
    def filter(self, message):
        return message.text in Values_3
filter_3_3 = Filter33()

class Filter2Keywords(BaseFilter):
    def filter(self, message):
        return message.text in TwoSteps_Keywords
filter_2_keywords = Filter2Keywords()

class Filter21(BaseFilter):
    def filter(self, message):
        return message.text in Values_1
filter_2_1 = Filter21()

class Filter22(BaseFilter):
    def filter(self, message):
        return message.text in Values_2
filter_2_2 = Filter22()

@restricted
def step_one_of_three(bot, update):
    global Keyword
    Keyword = update.message.text
    my_log("User %s, ID %s: Keyword gesendet: %s", update.effective_user.full_name, update.effective_user.id, Keyword)
    global Values_1
    for elem in xml_root.find('ThreeSteps').find(Keyword):
        Values_1.append(elem.tag)
    reply_markup = ReplyKeyboardMarkup(build_menu(Values_1,3))
    update.message.reply_text(xml_root.find('ThreeSteps').find(Keyword).attrib['q1'],reply_markup=reply_markup)
    return 1

@restricted
def step_two_of_three(bot, update):
    global StepOne
    StepOne = update.message.text
    my_log("User %s, ID %s: StepOne gewählt: %s", update.effective_user.full_name, update.effective_user.id, StepOne)
    global Values_2
    for elem in xml_root.find('ThreeSteps').find(Keyword).find(StepOne):
        Values_2.append(elem.tag)
    reply_markup = ReplyKeyboardMarkup(build_menu(Values_2,2))
    update.message.reply_text(xml_root.find('ThreeSteps').find(Keyword).attrib['q2'],reply_markup=reply_markup)
    return 2


@restricted
def step_three_of_three(bot, update):
    global StepTwo
    StepTwo = update.message.text
    my_log("User %s, ID %s: StepTwo gewählt: %s", update.effective_user.full_name, update.effective_user.id, StepTwo)
    global Values_3
    for elem in xml_root.find('ThreeSteps').find(Keyword).find(StepOne).find(StepTwo):
        Values_3.append(elem.text)
    reply_markup = ReplyKeyboardMarkup(build_menu(Values_3,2))
    update.message.reply_text(xml_root.find('ThreeSteps').find(Keyword).attrib['q3'],reply_markup=reply_markup)
    return 3

@restricted
def action_of_three_steps(bot, update):
    global StepThree
    StepThree = update.message.text
    my_log("User %s, ID %s: StepThree gewählt: %s", update.effective_user.full_name, update.effective_user.id, StepThree)
    item_name = xml_root.find('ThreeSteps').find(Keyword).find(StepOne).find(StepTwo).attrib['name']
    if send_oh(item_name,StepThree):
        reply = 'OK 👍🏻 sollte erledigt sein.'
        my_log("User %s, ID %s: Aktion: Setze Item %s auf %s", update.effective_user.full_name, update.effective_user.id, item_name, StepThree) 
    else:
        reply = 'Oh 😳 da ist leider was schief gegangen, sorry!'
        my_log("User %s, ID %s: Aktion: Setze Item %s auf %s - FEHLER!", update.effective_user.full_name, update.effective_user.id, item_name, StepThree) 
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    initialize_vars()
    return ConversationHandler.END

@restricted
def step_one_of_two(bot, update):
    global Keyword
    Keyword = update.message.text
    my_log("User %s, ID %s: Keyword gesendet: %s", update.effective_user.full_name, update.effective_user.id, Keyword)
    global Values_1
    for elem in xml_root.find('TwoSteps').find(Keyword):
        Values_1.append(elem.tag)
    reply_markup = ReplyKeyboardMarkup(build_menu(Values_1,3))
    update.message.reply_text(xml_root.find('TwoSteps').find(Keyword).attrib['q1'],reply_markup=reply_markup)
    return 1

@restricted
def step_two_of_two(bot, update):
    global StepOne
    StepOne = update.message.text
    my_log("User %s, ID %s: StepOne gewählt: %s", update.effective_user.full_name, update.effective_user.id, StepOne)
    global Values_2
    for elem in xml_root.find('TwoSteps').find(Keyword).find(StepOne):
        Values_2.append(elem.text)
    reply_markup = ReplyKeyboardMarkup(build_menu(Values_2,4))
    update.message.reply_text(xml_root.find('TwoSteps').find(Keyword).attrib['q2'],reply_markup=reply_markup)
    return 2

@restricted
def action_of_two_steps(bot, update):
    global StepTwo
    StepTwo = update.message.text
    my_log("User %s, ID %s: StepTwo gewählt: %s", update.effective_user.full_name, update.effective_user.id, StepTwo)
    item_name = xml_root.find('TwoSteps').find(Keyword).find(StepOne).attrib['name']
    if send_oh(item_name,StepTwo):
        reply = 'OK 👍🏻 sollte erledigt sein.'
        my_log("User %s, ID %s: Aktion: Setze Item %s auf %s", update.effective_user.full_name, update.effective_user.id, item_name, StepTwo)
    else:
        reply = 'Oh 😳 da ist leider was schief gegangen, sorry!'
        my_log("User %s, ID %s: Aktion: Setze Item %s auf %s - FEHLER!", update.effective_user.full_name, update.effective_user.id, item_name, StepTwo)
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    initialize_vars()
    return ConversationHandler.END

@restricted
def cancel(bot, update):
    my_log("User %s, ID %s: Abbruch", update.effective_user.full_name, update.effective_user.id) 
    update.message.reply_text('abgebrochen',reply_markup=ReplyKeyboardRemove())
    initialize_vars()
    return ConversationHandler.END

@restricted
def help_me(bot, update):
    all_keywords = ThreeSteps_Keywords + TwoSteps_Keywords + ['Temperaturen (anzeigen)','Müll (erledigt)','Guten Morgen','Feierabend']
    reply = "Hallo, ich bin's, " + bot_name + " 😊\nIch kümmer mich ein bisschen um euer Haus wenn's dir recht ist."
    reply += "\nSchick mir einfach eines der folgenden Worte - wenn ich dazu noch mehr wissen muss, dann fag ich dich...\n"
    reply_markup = ReplyKeyboardMarkup(build_menu(all_keywords,2))
    update.message.reply_text(reply,reply_markup=reply_markup)

@restricted
def show_temps(bot, update):
    reply = "=== 🔥 Temperaturen ❄️ ==="
    reply += "\n" + "Draußen: " + "{:.1f}".format(get_oh('TempAktuellFIO'))
    reply += "\n" + "Wohnzimmer: " "{:.1f}".format(+ get_oh('T_WZ_ist'))
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    my_log("User %s, ID %s: Temperaturen angefragt", update.effective_user.full_name, update.effective_user.id)

@restricted
def set_garbage(bot, update):
    if send_oh('Abfall_Steht_An','OFF'):
        reply = "OK, Müll ist also erledigt 🚚 <= 🗑️\nDanke ❤️"
        my_log("User %s, ID %s: Aktion: Setze Item Abfall_Steht_An auf OFF", update.effective_user.full_name, update.effective_user.id)
    else:
        reply = "OK, Müll ist also erledigt 🚚 <= 🗑️\nDanke ❤️\nLeider konnte ich es aber dem System nicht sagen, da ein Fehler aufgetreten ist. Tut mir leid!"
        my_log("User %s, ID %s: Aktion: Setze Item Abfall_Steht_An auf OFF - FEHLER", update.effective_user.full_name, update.effective_user.id) 
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())

@restricted
def good_morning(bot, update):
    t_out = get_oh('TempAktuellFIO')
    reply = "Guten Morgen! ☺️"
    reply += "\n" + "Draußen hat es " + "{:.1f}".format(t_out) + " °C"
    if t_out < 3:
        reply += " ❄️"
    reply += "\n" + "im Wohnzimmer " + "{:.1f}".format(get_oh('T_WZ_ist')) + " °C"
    reply += "\nZur Arbeit brauchst du aktuell " + str(maps_driving_time(coord_home,coord_work1)) + " Minuten"
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    my_log("User %s, ID %s: Guten Morgen gesagt", update.effective_user.full_name, update.effective_user.id)

@restricted
def time_to_work(bot, update):
    reply = "\nZur Arbeit brauchst du aktuell " + str(maps_driving_time(coord_home,coord_work1)) + " Minuten."
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    my_log("User %s, ID %s: Zeit zur Arbeit angefragt", update.effective_user.full_name, update.effective_user.id)

@restricted
def time_home(bot, update):
    reply = "\nVon der Arbeit nach Hause brauchst du aktuell " + str(maps_driving_time(coord_work1,coord_home)) + " Minuten."
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    my_log("User %s, ID %s: Zeit Arbeit nach Hause angefragt", update.effective_user.full_name, update.effective_user.id)

@restricted
def chat_id(bot, update):
    reply = "Unsere Chat-ID ist:\n"
    reply += update.message.chat_id
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    my_log("User %s, ID %s: Chat-id angefragt. Sie ist: %s", update.effective_user.full_name, update.effective_user.id, update.message.chat_id)

@restricted
def thanks(bot, update):
    reply = "Gerne 😘"
    update.message.reply_text(reply,reply_markup=ReplyKeyboardRemove())
    my_log("User " + update.effective_user.full_name + " ID " + str(update.effective_user.id) + ": Danke gesagt - sehr freundlich")

def error(bot, update, error):
    """Log Errors caused by Updates."""
    try:
        raise error
    except Unauthorized:
        my_log('Update "%s" caused the error: "%s"', update, error)
    except BadRequest:
        my_log('Update "%s" caused the error: "%s"', update, error)
    except TimedOut:
        pass
    except NetworkError:
        pass
    except ChatMigrated as e:
        my_log('Update "%s" caused the error: "%s"', update, error)
    except TelegramError:
        my_log('Update "%s" caused the error: "%s"', update, error)

def main():
    initialize_vars()
    global Items
    try: # for my test system that does not have a connection to openhab
        openhab = openHAB(url_oh)
        Items = openhab.fetch_all_items()
    except Exception as e:
        my_log("Error connecting to openHAB: %s", e)
        pass

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(token=config['KEYS']['bot_api'])

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler
    conv_handler_3 = ConversationHandler(
        entry_points=[MessageHandler(filter_3_keywords, step_one_of_three)],

        states={
            1: [MessageHandler(filter_3_1, step_two_of_three)],

            2: [MessageHandler(filter_3_2, step_three_of_three)],

            3: [MessageHandler(filter_3_3, action_of_three_steps)],

        },

        #fallbacks=[RegexHandler('^(Abbruch|abbruch|cancel|stop|Stop|Stopp|stopp)$', cancel)]
        fallbacks=[MessageHandler(Filters.all, cancel)]
    )

    conv_handler_2 = ConversationHandler(
        entry_points=[MessageHandler(filter_2_keywords, step_one_of_two)],

        states={
            1: [MessageHandler(filter_2_1, step_two_of_two)],

            2: [MessageHandler(filter_2_2, action_of_two_steps)],

        },

        #fallbacks=[RegexHandler('^(Abbruch|abbruch|cancel|stop|Stop|Stopp|stopp)$', cancel)]
        fallbacks=[MessageHandler(Filters.all, cancel)]
    )

    help_handler = RegexHandler('^(Hilfe|hilfe|Start|start|Hallo|hallo)$',help_me)
    start_handler = CommandHandler('start',help_me)
    temp_handler = RegexHandler('^(Temp|temp)',show_temps)
    garbage_handler = RegexHandler('^(Müll)',set_garbage)
    good_morning_handler = RegexHandler('^((Guten|guten).(Morgen|morgen))',good_morning)
    time_to_work_handler = RegexHandler('^(Arbeit|arbeit)',time_to_work)
    time_home_handler = RegexHandler('^(Feierabend|feierabend|nach Hause|Nach Hause|heim|Heim)',time_home)
    chat_id_handler = RegexHandler('^(Chat|chat)',chat_id)
    thanks_handler = RegexHandler('^(Danke|danke)',thanks)

    dp.add_handler(conv_handler_3)
    dp.add_handler(conv_handler_2)
    dp.add_handler(help_handler)
    dp.add_handler(start_handler)
    dp.add_handler(temp_handler)
    dp.add_handler(garbage_handler)
    dp.add_handler(good_morning_handler)
    dp.add_handler(time_to_work_handler)
    dp.add_handler(time_home_handler)
    dp.add_handler(chat_id_handler)
    dp.add_handler(thanks_handler)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
