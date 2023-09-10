import os, requests, configparser
from tinydb import TinyDB, Query
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    constants,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
CLIENT_ID = CONFIG["Strava"]["CLIENT_ID"]
CLIENT_SECRET = CONFIG["Strava"]["CLIENT_SECRET"]
REDIRECT_URL = CONFIG["Server"]["URL"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()
STATUSES = {
    "ready": "Your activity is ready.",
    "wait": "Your activity is still being processed.",
    "deleted": "The created activity has been deleted.",
    "error": "There was an error processing your activity.",
}


def user_exists(user_id: str, db: TinyDB, query: Query) -> bool:
    user = db.search(query["user_id"] == user_id)
    if user:
        return True
    else:
        return False


def scopes_valid(user_id: str, db: TinyDB, query: Query) -> bool:
    if not user_exists(user_id, db, query):
        return False
    else:
        scope = db.get(query["user_id"] == user_id)["scope"]
        if "activity:write" in scope:
            return True
        else:
            return False


async def get_strava_refresh_token(user_id: str, client_id: str, client_secret: str, db: TinyDB, query: Query) -> str:
    refresh_token = db.get(query["user_id"] == user_id)["refresh_token"]
    if not refresh_token:
        url = f"https://www.strava.com/api/v3/oauth/token"
        code = db.get(query["user_id"] == user_id)["auth_code"]
        params = {
            "client_id": f"{client_id}",
            "client_secret": f"{client_secret}",
            "grant_type": "authorization_code",
            "code": f"{code}",
        }
        response = requests.post(url, params=params)
        refresh_token = response.json()["refresh_token"]
    return refresh_token


async def get_strava_access_token(user_id: str, client_id: str, client_secret: str, refresh_token: str, db: TinyDB, query: Query) -> str:
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    refresh_token = response.json()["refresh_token"]
    db.update({"refresh_token": str(refresh_token)}, query["user_id"] == user_id)
    access_token = response.json()["access_token"]
    return access_token


async def upload_strava_activity(access_token: str, activity_name: str, data_type: str, file: bytes) -> str:
    url = "https://www.strava.com/api/v3/uploads"
    params = (
        {
            "name": activity_name,
            "description": "t.me/StravaUploadActivityBot",
            "data_type": data_type,
        }
        if activity_name != "⏩"
        else {
            "description": "t.me/StravaUploadActivityBot",
            "data_type": data_type,
        }
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {"file": file}
    response = requests.post(url, params=params, headers=headers, files=files)
    upload_id = response.json()["id_str"]
    return upload_id


async def get_strava_upload_status(upload_id: str, access_token: str, statuses: dict):
    url = f"https://www.strava.com/api/v3/uploads/{upload_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        upload = requests.get(url, headers=headers).json()
        if upload["status"] != statuses["wait"]:
            return upload


# /start; регистрация
async def start(update: Update):
    user_id = str(update.message.from_user.id)
    inline_key = InlineKeyboardButton(
        "Открыть Strava 🔑",
        url=f"http://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&scope=activity:write&redirect_uri={REDIRECT_URL}?user_id={user_id}",
    )
    inline_keyboard = InlineKeyboardMarkup([[inline_key]])
    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            "🤖 Привет! Я бот, который поможет тебе публиковать твою активность в Strava. Для этого мне нужно получить твое разрешение на загрузку файлов в твой аккаунт. Нажми кнопку ниже, чтобы продолжить.",
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
    else:
        await update.message.reply_text(
            "🤖 Мы уже знакомы. Но если ты хочешь переавторизовать меня в Strava, нажми кнопку ниже.",
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )


# /favorites; создание списка избранных названий
async def favorites_start(update: Update):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            "🤖 Прости, но я тебя пока не знаю. Чтобы я мог тебе помочь, сначала введи команду /start и выполни пару шагов.",
            constants.ParseMode.MARKDOWN,
        )
        return
    else:
        await update.message.reply_text(
            "🤖 Введи до 3-х названий через запятую и я добавлю их в избранное.",
            constants.ParseMode.MARKDOWN,
        )
    return "favorites_finish"


async def favorites_finish(update: Update):
    user_id = str(update.message.from_user.id)
    favorites = update.message.text.split(",")[:3]
    for fav in favorites:
        fav.strip()
    USER_DB.upsert({"favorites": favorites}, USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        f"🤖 Готово!",
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /delete; удаление данных пользователя из userdata.json
async def delete_start(update: Update):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            "🤖 Прости, но я тебя пока не знаю. Чтобы я мог тебе помочь, сначала введи команду /start и выполни пару шагов.",
            constants.ParseMode.MARKDOWN,
        )
        return
    else:
        await update.message.reply_text(
            "🤖 Ты точно хочешь чтобы я удалил все твои данные? Я больше не смогу работать с твоей Strava, пока ты снова мне не разрешить.\nДля подтверждения повтори команду /delete, для отмены /cancel.",
            constants.ParseMode.MARKDOWN,
        )
    return "delete_finish"


async def delete_finish(update: Update):
    user_id = str(update.message.from_user.id)
    USER_DB.remove(USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        "🤖 Готово!",
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Публикация активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            "🤖 Прости, но я тебя пока не знаю. Чтобы я мог тебе помочь, сначала введи команду /start и выполни пару шагов.",
            constants.ParseMode.MARKDOWN,
        )
        return
    elif not scopes_valid(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            "🤖 Кажется, у меня не хватает прав, чтобы опубликовать активность. Пожалуйста, выполни команду /start еще раз.",
            constants.ParseMode.MARKDOWN,
        )
        return

    file_id = update.message.document.file_id
    file_data = await context.bot.get_file(file_id)
    context.user_data["file_name"] = update.message.document.file_name
    context.user_data["file_path"] = file_data.file_path

    activity_keys = ["⏩"]
    favorites = USER_DB.get(USER_QUERY["user_id"] == user_id)["favorites"]
    for fav in favorites:
        activity_keys.append(fav)
    activity_keyboard = ReplyKeyboardMarkup(
        [activity_keys],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Имя активности",
    )
    await update.message.reply_text(
        "🤖 Выбери имя активности и я её опубликую.",
        constants.ParseMode.MARKDOWN,
        reply_markup=activity_keyboard,
    )
    return "upload_finish"


async def upload_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    activity_name = update.message.text

    refresh_token = await get_strava_refresh_token(user_id, CLIENT_ID, CLIENT_SECRET, USER_DB, USER_QUERY)
    access_token = await get_strava_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    data_type = str.split(context.user_data["file_name"], ".")[-1]
    file = requests.get(context.user_data["file_path"]).content

    upload_id = await upload_strava_activity(access_token, activity_name, data_type, file)

    upload = await get_strava_upload_status(upload_id, access_token, STATUSES)
    if upload["status"] == STATUSES["ready"]:
        inline_key = InlineKeyboardButton(
            "Посмотреть",
            url=f"https://www.strava.com/activities/{upload['activity_id']}",
        )
        inline_keyboard = InlineKeyboardMarkup([[inline_key]])
        await update.message.reply_text(
            "Активность опубликована 🏆",
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
    elif upload["status"] == STATUSES["error"]:
        await update.message.reply_text(
            f"Не удалось загрузить активность 💢\nДетали: `{upload['error']}`",
            constants.ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    elif upload["status"] == STATUSES["deleted"]:
        await update.message.reply_text(
            f"Не удалось загрузить активность 💢\nДетали: `{upload['status']}`",
            constants.ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    return ConversationHandler.END


# /help; справка
async def help(update: Update):
    help_text = f""
    await update.message.reply_text(help_text, constants.ParseMode.MARKDOWN)


# /cancel; отмена диалога ConversationHandler
async def cancel(update: Update):
    await update.message.reply_text(
        "Действие отменено ↩️",
        constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# Обработка прочего текста
async def other(update: Update):
    await update.message.reply_text(
        "🤖 К сожалению, я не понимаю, что ты имеешь ввиду.\nПопробуй ввести команду /help.",
        constants.ParseMode.MARKDOWN,
    )


def main():
    application = ApplicationBuilder().token(TOKEN).build()
    delete_dialog = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={"delete_finish": [CommandHandler("delete", delete_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    favorites_dialog = ConversationHandler(
        entry_points=[CommandHandler("favorites", favorites_start)],
        states={"favorites_finish": [MessageHandler(filters.TEXT, favorites_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    upload_dialog = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Document.FileExtension("fit") | filters.Document.FileExtension("tcx") | filters.Document.FileExtension("gpx"),
                upload_start,
            )
        ],
        states={"upload_finish": [MessageHandler(~filters.COMMAND & filters.TEXT, upload_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(upload_dialog)
    application.add_handler(delete_dialog)
    application.add_handler(favorites_dialog)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(
        MessageHandler(
            ~filters.COMMAND & ~filters.Document.FileExtension("fit") & ~filters.Document.FileExtension("tcx") & ~filters.Document.FileExtension("gpx"),
            other,
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()
