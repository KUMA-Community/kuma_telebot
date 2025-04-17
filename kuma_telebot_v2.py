import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import subprocess
import socket
import threading
from configparser import ConfigParser
from telebot import types
import logging
import signal
import os
import re
import requests
import json
import urllib3.exceptions
from datetime import datetime

# coding: utf8

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
config = ConfigParser()
config.read("/opt/kaspersky/kuma/correlator/0b9200ae-d5a9-41ce-bf7b-c16814ed9524/scripts/bot.conf")
logger = telebot.logger
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
telebot.logger.setLevel(logging.DEBUG)

# Переменные - START
BOT_TOKEN = config["Settings"]["BOT_TOKEN"]
bot = telebot.TeleBot(BOT_TOKEN)
RestrictedCommands = config["Settings"]["RestrictedCommands"].split(',')
allowed_users = []
for key in config['AllowedUsers']: allowed_users.append(int(key))
ruleNameRegex = r"Правило:\s+(.*?)\n"
kumaAddr = config["Settings"]["kumaAddr"]
kumaBearer = config["Settings"]["kumaBearer"]
kumaGetAlerts = "https://"+kumaAddr+":7223/api/v1/alerts/"
kumaCloseAlerts = "https://"+kumaAddr+":7223/api/v1/alerts/close"
kumaServices = "https://"+kumaAddr+":7223/api/v1/services"
kumaBackup = "https://"+kumaAddr+":7223/api/v1/system/backup"
backup_dir = "/tmp"
os.makedirs(backup_dir, exist_ok=True)  # Ensure /tmp exists
backupName = os.path.join(backup_dir, f"kuma_backup_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.tar.gz")
headers = {"Authorization": "Bearer " + kumaBearer}
kumaUser = config["Settings"]["kumaUser"]
kumaPassword = config["Settings"]["kumaPassword"]
cooks = {}
cookie_value = ""
reps = []
session = requests.Session()
# Переменные - END


def privateApi():
    url = f'https://{kumaAddr}:7220/api/login'
    x_kuma_location = f'https://{kumaAddr}:7220/login'

    body = {
    'login': kumaUser,
    'password': kumaPassword
    }

    headersPriv = {'x-kuma-location': x_kuma_location}    
    response = session.post(url, headers=headersPriv, data=json.dumps(body), verify=False)

    if response.status_code == 200:
        xsrf_token = re.match('XSRF-TOKEN=([^;]+)', response.headers['Set-Cookie']).group(1)
        kuma_m_sid = re.match('.+kuma_m_sid=([^;]+)', response.headers['Set-Cookie']).group(1)
        cookie_value = 'XSRF-TOKEN='+xsrf_token+'; kuma_m_sid='+kuma_m_sid+'; x-xsrf-token: '+xsrf_token
        headersPriv = {'cookie': cookie_value}
        return cooks
cooks = privateApi()

def find_id_by_substring(json_data, search_substring):
    matching_ids = [item.get('id') for item in json_data if search_substring.lower() in item.get('name').lower() and item.get('status').lower() != "closed"]
    return matching_ids


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.from_user.id in allowed_users:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button_hello = types.KeyboardButton(f"🕹️ Активные сервисы")
        button_hello2 = types.KeyboardButton(f"🕹️ Backup")
        button_hello3 = types.KeyboardButton(f"🕹️ Список отчетов")
        markup.add(button_hello, button_hello2, button_hello3)
        bot.reply_to(message, f"Да, владыка, приказывай!", reply_markup=markup)
    else:
        bot.reply_to(message, f"У тебя нет доступа ко мне!")

@bot.message_handler(func=lambda message: message.text.startswith('\\cmd ') or message.text.startswith(r'\cmd '))
def execute_command(message):
    if message.from_user.id in allowed_users:
        try:
            # Выполнение команды после ключа \cmd
            command = message.text.split('\\cmd ')[1] if '\\cmd ' in message.text else message.text.split(r'\cmd ')[1]
            # Ограничения на выполнение команд для безопасности     ['rm', 'sudo', 'shutdown', 'passwd', 'reboot', 'init']
            if any(forbidden in command for forbidden in RestrictedCommands):
                raise ValueError(f"Использование запрещенной команды!")
            process = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            response = process.stdout if process.stdout else process.stderr
            bot.reply_to(message, response)
        except Exception as e:
            bot.reply_to(message, f"Error occured:\n\n{str(e)}")
    else:
        bot.reply_to(message, f"У тебя нет доступа ко мне!")


@bot.message_handler(func=lambda message: message.text.startswith(f"🕹️"))
def handle_hello_world(message):
    if message.from_user.id in allowed_users:
        chat_id = message.chat.id
        if message.text == "🕹️ Активные сервисы":
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, f"Активные сервисы: 🔽")
            response = requests.request("GET", kumaServices, headers=headers, verify=False)
            json_data = json.loads(response.text)
            string_acc = ""
            light = ""
            print(json_data)
            for item in json_data:
                if item.get('status') == "green":
                    light = "🟢"
                elif item.get('status') == "blue":
                    light = "🔵"
                elif item.get('status') == "yellow":
                    light = "🟡"                
                else:
                    light = "🔴"
                string_acc += light + " " + item.get('name') + "\n"
            bot.send_message(chat_id, string_acc)
        if message.text == "🕹️ Backup":
            response = requests.request("GET", kumaBackup, headers=headers, verify=False)
            bot.send_message(chat_id, f"Идет формирование архива, ожидайте... ⌛")            
            with open(backupName, "wb") as f:
                f.write(response.content)
            backup_size = os.path.getsize(backupName) >> 20
            if int(response.status_code) == 200:
                bot.delete_message(chat_id, message.message_id)
                bot.send_message(chat_id, f"✅ Бекап успешно создан!\n{backupName}\nРазмер: {backup_size} MB")
            else:
                bot.delete_message(chat_id, message.message_id)
                bot.send_message(chat_id, f"⛔ С бекапом что-то пошло не так!")
        if message.text == "🕹️ Список отчетов":                
            url = f'https://{kumaAddr}:7220/api/private/reports/?order=-createdAt&limit=250'
            response = session.get(url, headers = cooks, verify=False)
            if int(response.status_code) == 200:
                bot.delete_message(chat_id, message.message_id)
                json_data = json.loads(response.text)
                global reps
                reps = []
                cnt = 0
                for item in json_data:
                    string = "{\"cmd\":\"/report_" + str(cnt) + "\",\"num\":\"" + str(cnt) + "\",\"id\":\"" +  item.get('id') + "\",\"name\":\"" + item.get('name') + "\",\"date\":\"" + str(datetime.fromtimestamp(item.get('createdAt') / 1000)) + "\"}"
                    reps.append(string)
                    cnt += 1
                bot.send_message(chat_id, f"{str(reps)[1:-1]}")
            else:
                bot.delete_message(chat_id, message.message_id)
                bot.send_message(chat_id, f"⛔ С отчетом что-то пошло не так!")
    else:
        bot.reply_to(message, f"У тебя нет доступа ко мне!")

@bot.message_handler(func=lambda message: message.text.startswith('//report_') or message.text.startswith(r'/report_'))
def execute_command(message):
    if message.from_user.id in allowed_users:
        try:
            # Загрузка отчета по его номеру num, пример: \report 6                       
            report_id =""
            report_num = message.text.split('/report_')[1]
            bot.reply_to(message, report_num)            
            
            try:
                report_id = json.loads(reps[int(report_num)])
            except IndexError:
                report_id = "null"            

            if not report_id == "null":
                url = f'https://{kumaAddr}:7220/api/private/reports/id/{report_id["id"]}/download?format=pdf'
                bot.send_message(message.chat.id, f"Файл загружается...")
                response = session.get(url, headers = cooks, verify=False)                
                if int(response.status_code) == 200:
                    with open("/opt/kaspersky/kuma/correlator/0b9200ae-d5a9-41ce-bf7b-c16814ed9524/scripts/doc.pdf", "wb") as f:
                        f.write(response.content)
                        f.close()                    
                    doc = open("/opt/kaspersky/kuma/correlator/0b9200ae-d5a9-41ce-bf7b-c16814ed9524/scripts/doc.pdf", "rb")
                    bot.send_document(message.chat.id, doc)
                    doc.close()                   
                else:
                    bot.reply_to(message, f"⛔ Не удалось получить отчет!")
            else:
                bot.reply_to(message, f"⛔ С отчетом что-то пошло не так!")
        except Exception as e:
            bot.reply_to(message, f"Error occured:\n\n{str(e)}")
    else:
        bot.reply_to(message, f"У тебя нет доступа ко мне!")

# Функция для обработки входящих TCP соединений и сообщений
# nc 127.0.0.1 16667 <<< $'⚠️Алерт \n$NAME\nТекст после новой строки'
#@bot.message_handler(func=lambda message: True)
def tcp_server():
    host = '127.0.0.1'
    port = 16667

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)

    while True:
        try:
            client_socket, client_address = server_socket.accept()
            message = client_socket.recv(1024).decode('utf-8')
            for chat_id in allowed_users:
                # Create a reply markup with a button
                #bot.send_message(chat_id, message, parse_mode='HTML', reply_markup=gen_markup())
                keyboard = types.InlineKeyboardMarkup()
                # Отправляем сообщение чтобы появился его ID
                sent_message = bot.send_message(chat_id, message, parse_mode='HTML', reply_markup=keyboard)
                button = types.InlineKeyboardButton(text=f"Закрыть алерт", callback_data=f"button_pressed_{sent_message.message_id}")
                keyboard.add(button)
                # Редактируем и добавляем обработчик нажатия callback_data
                bot.edit_message_reply_markup(chat_id, sent_message.message_id, reply_markup=keyboard)
                # Запоминаем идентификатор отправленного сообщения
                #bot.register_next_step_handler(sent_message, process_callback)
            client_socket.close()
        except Exception as e:
            bot.reply_to(message, f"Error occured while tcp message received:\n\n{str(e)}")

# Обработчик сигнала завершения работы
def handle_exit(signum, frame):
    global tcp_server_running
    logging.info("Received signal to exit. Stopping TCP server.")
    tcp_server_running = False
    os._exit(0)

# Устанавливаем обработчик сигнала завершения работы
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


#def process_callback(message):
#    # В этой функции вы можете обрабатывать дополнительные шаги после того, как пользователь нажал на кнопку
#    pass

@bot.callback_query_handler(func=lambda call: True)
def handle_button_click(call):
    print(call.message.from_user.id)
    print(call.message.from_user)
    print(call.message)
    print("||||||||||||||||||||||||")
    if call.message.from_user.id in allowed_users:
        if call.data.startswith("button_pressed_"):
            chat_id = call.message.chat.id
            try:
                #bot.send_message(chat_id, f"Вы нажали кнопку и вот текст сообщения:\n{call.message.text}")
                
                matches = re.findall(ruleNameRegex, call.message.text)
                # Выводим первое найденное совпадение
                if matches:
                    search_substring = matches[0]
                    search_substring = search_substring[:-2]
                    response = requests.request("GET", kumaGetAlerts, headers=headers, verify=False)
                    json_data = json.loads(response.text)
                    #print(json_data)
                    result_ids = find_id_by_substring(json_data, search_substring)
                    #print(result_ids)
                    # перечисляем все ID алертов с совпадением с подстрокой поиска
                    if result_ids:
                        print(f"Найдены совпадения для подстроки '{search_substring}', соответствующие ID:")
                        for item_id in result_ids:        
                            payload = json.dumps({"id": item_id, "reason": "responded"})
                            response = requests.request("POST", kumaCloseAlerts, headers=headers, data=payload, verify=False)
                            if int(response.status_code) == 204:
                                bot.send_message(chat_id, f"Алерт: {search_substring}\nID: {item_id}\nЗАКРЫТ")
                    else:
                        print(f"Нет совпадений для подстроки '{search_substring}'.")
                        bot.send_message(chat_id, f"Алерт: {search_substring} ОТСУТСТВУЕТ")
                    #bot.send_message(chat_id, f"Совпадение: {result}")
                else:
                    print(r"Совпадения не найдены.")           
                bot.delete_message(chat_id, call.message.message_id)
            except ValueError:
                logging.error("Invalid message_id in callback_data.")
            except telebot.apihelper.ApiException as api_exception:
                logging.error(f"Telegram API exception: {api_exception}")
    else:
        bot.reply_to(call.message, f"У тебя нет доступа ко мне!")

# Запуск сервера в отдельном потоке
tcp_thread = threading.Thread(target=tcp_server)
tcp_thread.start()

# Запуск бота
if __name__ == "__main__":
   bot.polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
