# TODO Добавить обработку команды для удаления user'а из базы
# TODO Добавить зависимость команд /start и /help от наличия юзера в базе

import os, requests, aiofiles, configparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from tinydb import TinyDB, Query
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))


# Обработка /start; Вывод приветствия
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    client_id = config["Strava"]["CLIENT_ID"]
    redirect_uri = config["Server"]["URL"]
    inline_button = InlineKeyboardButton("Перейти к Strava", url=f"http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&scope=activity:write&redirect_uri={redirect_uri}?user_id={user_id}")
    inline_keyboard = InlineKeyboardMarkup([[inline_button]])
    await update.message.reply_text("Привет! Я помогу вам опубликовать активность в Strava.\nДля начала, разрешите мне загружать файлы в Strava от вашего имени 👇", reply_markup=inline_keyboard)


# Обработка /help; Вывод информационного сообщения
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    client_id = config["Strava"]["CLIENT_ID"]
    redirect_uri = config["Server"]["URL"]
    text = f"""Как публиковать активность в Strava с помощью бота:\n
    1. Перейдите по ссылке [https://www.strava.com/oauth](http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&scope=activity:write&redirect_uri={redirect_uri}?user_id={user_id})
    2. В открывшемся окне нажмите *Разрешить*
    3. Пришлите в чат файл формата `.fit`, `.tcx` или `.gpx`
    4. Бот автоматически опубликует вашу активность"""
    await update.message.reply_text(text, constants.ParseMode.MARKDOWN)


# Обработка прочего текста
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("К сожалению, я не знаю, что на это ответить 🤖\nПопробуйте ввести команду `/help`.", constants.ParseMode.MARKDOWN)


# Загрузка активности в Strava
async def upload_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    client_id = config["Strava"]["CLIENT_ID"]
    client_secret = config["Strava"]["CLIENT_SECRET"]
    file_id = update.message.document.file_id
    file_name = update.message.document.file_name
    file_data = await context.bot.get_file(file_id)
    db = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
    user = Query()

    # Получение файла от API Telegram и запись в файл на сервер
    async with aiofiles.open(os.path.join(os.path.dirname(__file__), "..", "storage", file_name), "wb") as bytes:
        await bytes.write(requests.get(file_data.file_path).content)

    # Попытка получить refresh_token из БД; при неуспехе получаем от API
    try:
        refresh_token = db.get(user["user_id"] == user_id)["refresh_token"]
    except (IndexError, KeyError):
        code = db.get(user["user_id"] == user_id)["auth_code"]
        url = f"https://www.strava.com/api/v3/oauth/token"
        params = {
            "client_id": f"{client_id}",
            "client_secret": f"{client_secret}",
            "grant_type": "authorization_code",
            "code": f"{code}",
        }
        response = requests.post(url, params=params)
        refresh_token = response.json()["refresh_token"]

    # Получение access_token и обновление refresh_token
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    bearer = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]
    db.update({"refresh_token": refresh_token}, user["user_id"] == user_id)

    # Загрузка файла в Strava
    async with aiofiles.open(os.path.join(os.path.dirname(__file__), "..", "storage", file_name), "rb") as bytes:
        file = await bytes.read()
    url = "https://www.strava.com/api/v3/uploads"
    params = {"data_type": file_name.split(".")[-1], "activity_type": "run"}
    headers = {"Authorization": f"Bearer {bearer}"}
    files = {"file": file}
    response = requests.post(url, params=params, headers=headers, files=files)
    if response.status_code == 201:
        upload_id = response.json()["id_str"]
    else:
        await update.message.reply_text(f'Не удалось загрузить активность 🥵\nДетали: `{response.json()["errors"]}`', constants.ParseMode.MARKDOWN)
        return
    
    # Проверка статуса загрузки
    url = f"https://www.strava.com/api/v3/uploads/{upload_id}"
    headers = {"Authorization": f"Bearer {bearer}"}
    statuses = {
        "ready": "Your activity is ready.",
        "wait": "Your activity is still being processed.",
        "deleted": "The created activity has been deleted.",
        "error": "There was an error processing your activity.",
    }
    while True:
        response = requests.get(url, headers=headers)
        if response.json()["status"] == statuses["wait"]:
            pass
        elif response.json()["status"] == statuses["ready"]:
            inline_button = InlineKeyboardButton("Посмотреть", url=f'https://www.strava.com/activities/{response.json()["activity_id"]}')
            inline_keyboard = InlineKeyboardMarkup([[inline_button]])
            await update.message.reply_text("Активность опубликована 👌", reply_markup=inline_keyboard)
            break
        elif response.json()["status"] == statuses["error"]:
            await update.message.reply_text(f'Не удалось загрузить активность 🥵\nДетали: `{response.json()["error"]}`', constants.ParseMode.MARKDOWN)
            break
        elif response.json()["status"] == statuses["deleted"]:
            await update.message.reply_text(f'Не удалось загрузить активность 🥵\nДетали: `{response.json()["status"]}`', constants.ParseMode.MARKDOWN)
            break

    try:
        os.remove(os.path.join(os.path.dirname(__file__), "..", "storage", file_name))
    except FileNotFoundError:
        pass


def main():
    token = config["Telegram"]["BOT_TOKEN"]
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(MessageHandler(filters.TEXT, other))
    application.add_handler(MessageHandler(filters.ATTACHMENT, upload_activity))

    application.run_polling()


if __name__ == "__main__":
    main()
