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
STATUSES = {
    "ready": "Your activity is ready.",
    "wait": "Your activity is still being processed.",
    "deleted": "The created activity has been deleted.",
    "error": "There was an error processing your activity.",
}


def user_exists(user_id: str, db: TinyDB) -> bool:
    query = Query()
    user = db.search(query["user_id"] == user_id)
    if user:
        return True
    else:
        return False


def scopes_valid(user_id: str, db: TinyDB) -> bool:
    query = Query()
    if not user_exists(user_id, db):
        return False
    else:
        scope = db.get(query["user_id"] == user_id)["scope"]
        if "activity:write" in scope:
            return True
        else:
            return False


async def get_strava_refresh_token(user_id: str, client_id: str, client_secret: str, db: TinyDB) -> str:
    query = Query()
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


async def get_strava_access_token(user_id: str, client_id: str, client_secret: str, refresh_token: str, db: TinyDB) -> str:
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    refresh_token = response.json()["refresh_token"]
    query = Query()
    db.update({"refresh_token": str(refresh_token)}, query["user_id"] == user_id)
    access_token = response.json()["access_token"]
    return access_token


async def post_strava_activity(access_token: str, activity_name: str, data_type: str, file: bytes) -> str:
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


# /start; регистрация
async def start(update: Update, client_id: str, redirect_url: str, db: TinyDB):
    user_id = str(update.message.from_user.id)
    inline_key = InlineKeyboardButton(
        "Открыть Strava 🔑",
        url=f"http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&scope=activity:write&redirect_uri={redirect_url}?user_id={user_id}",
    )
    inline_keyboard = InlineKeyboardMarkup([[inline_key]])
    if not user_exists(user_id, db):
        await update.message.reply_text(
            "🤖 Привет! Я помогу вам опубликовать активность в Strava.\nДля начала, разрешите мне загружать файлы в ваш профиль Strava.",
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
    else:
        await update.message.reply_text(
            "🤖 этот сидит там чешет колоду блядь",
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )


# /favorites; создание списка избранных названий
async def favorites_start(update: Update, db: TinyDB):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id, db):
        await update.message.reply_text(
            "🤖 ты кто такой сука?",
            constants.ParseMode.MARKDOWN,
        )
        return
    else:
        await update.message.reply_text(
            "🤖 Введите до 3 названий через запятую и я их запомню",
            constants.ParseMode.MARKDOWN,
        )
    return "favorites_finish"


async def favorites_finish(update: Update, db: TinyDB):
    user_id = str(update.message.from_user.id)
    favorites = update.message.text.split(",")[:3]
    for fav in favorites:
        fav.strip()
    query = Query()
    db.upsert({"favorites": favorites}, query["user_id"] == user_id)
    await update.message.reply_text(
        f"🤖 готово {favorites}",
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /delete; удаление данных пользователя из userdata.json
async def delete_start(update: Update, db: TinyDB):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id, db):
        await update.message.reply_text(
            "🤖 ты кто такой сука чтоб это сделать?",
            constants.ParseMode.MARKDOWN,
        )
        return
    else:
        await update.message.reply_text(
            "🤖 Вы точно хотите чтобы я удалил все ваши данные? Я не смогу публиковать файлы пока вы снова не авторизуете меня в Strava.\nДля подтверждения повторите /delete, для отмены введите /cancel.",
            constants.ParseMode.MARKDOWN,
        )
    return "delete_finish"


async def delete_finish(update: Update, db: TinyDB):
    user_id = str(update.message.from_user.id)
    query = Query()
    db.remove(query["user_id"] == user_id)
    await update.message.reply_text(
        "🤖 Готово, я вас больше не помню.",
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Публикация активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE, db: TinyDB):
    user_id = str(update.message.from_user.id)

    if not user_exists(user_id, db):
        await update.message.reply_text(
            "🤖 ты кто такой сука?",
            constants.ParseMode.MARKDOWN,
        )
        return
    elif not scopes_valid(user_id, db):
        await update.message.reply_text(
            "🤖 ты кто такой сука чтоб это сделать?",
            constants.ParseMode.MARKDOWN,
        )
        return

    file_id = update.message.document.file_id
    file_data = await context.bot.get_file(file_id)
    context.user_data["file_name"] = update.message.document.file_name
    context.user_data["file_path"] = file_data.file_path

    activity_keys = ["⏩"]
    query = Query()
    favorites = db.get(query["user_id"] == user_id)["favorites"]
    for fav in favorites:
        activity_keys.append(fav)
    activity_keyboard = ReplyKeyboardMarkup([activity_keys], resize_keyboard=True, one_time_keyboard=True, input_field_placeholder="Название активности")
    await update.message.reply_text(
        "🤖 Введите имя активности и я её опубликую.",
        constants.ParseMode.MARKDOWN,
        reply_markup=activity_keyboard,
    )
    return "upload_finish"


async def upload_finish(update: Update, context: ContextTypes.DEFAULT_TYPE, client_id: str, client_secret: str, statuses: dict, db: TinyDB):
    user_id = str(update.message.from_user.id)
    activity_name = update.message.text
    refresh_token = await get_strava_refresh_token(user_id, client_id, client_secret, db)
    access_token = await get_strava_access_token(user_id, client_id, client_secret, refresh_token, db)
    data_type = str.split(context.user_data["file_name"], ".")[-1]
    file = requests.get(context.user_data["file_path"]).content

    upload_id = await post_strava_activity(access_token, activity_name, data_type, file)

    url = f"https://www.strava.com/api/v3/uploads/{upload_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:  # Проверка статуса загрузки
        response = requests.get(url, headers=headers)
        if response.json()["status"] == statuses["wait"]:
            continue
        elif response.json()["status"] == statuses["ready"]:
            inline_key = InlineKeyboardButton(
                "Посмотреть",
                url=f"https://www.strava.com/activities/{response.json()['activity_id']}",
            )
            inline_keyboard = InlineKeyboardMarkup([[inline_key]])
            await update.message.reply_text(
                "Активность опубликована 🏆",
                constants.ParseMode.MARKDOWN,
                reply_markup=inline_keyboard,
            )
            break
        elif response.json()["status"] == statuses["error"]:
            await update.message.reply_text(
                f"Не удалось загрузить активность 💢\nДетали: `{response.json()['error']}`",
                constants.ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove(),
            )
            break
        elif response.json()["status"] == statuses["deleted"]:
            await update.message.reply_text(
                f"Не удалось загрузить активность 💢\nДетали: `{response.json()['status']}`",
                constants.ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove(),
            )
            break

    return ConversationHandler.END


# /cancel; отмена диалога ConversationHandler
async def cancel(update: Update):
    await update.message.reply_text(
        "Действие отменено ↩️",
        constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# /help; справка
async def help(update: Update):
    help_text = f"🤖 помощь.txt"
    await update.message.reply_text(help_text, constants.ParseMode.MARKDOWN)


# Обработка прочего текста
async def other(update: Update):
    await update.message.reply_text(
        "🤖 К сожалению, я не знаю, что на это ответить.\nПопробуйте ввести команду /help.",
        constants.ParseMode.MARKDOWN,
    )


def main(token: str, client_id: str, client_secret: str, redirect_url: str, statuses: dict, db: TinyDB):
    application = ApplicationBuilder().token(token).build()
    delete_dialog = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start(db=db))],
        states={"delete_finish": [CommandHandler("delete", delete_finish(db=db))]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    favorites_dialog = ConversationHandler(
        entry_points=[CommandHandler("favorites", favorites_start(db=db))],
        states={"favorites_finish": [MessageHandler(filters.TEXT, favorites_finish(db=db))]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    upload_dialog = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Document.FileExtension("fit") | filters.Document.FileExtension("tcx") | filters.Document.FileExtension("gpx"), upload_start(db=db)
            )
        ],
        states={
            "upload_finish": [
                MessageHandler(~filters.COMMAND & filters.TEXT, upload_finish(client_id=client_id, client_secret=client_secret, statuses=statuses, db=db))
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(upload_dialog)
    application.add_handler(delete_dialog)
    application.add_handler(favorites_dialog)
    application.add_handler(CommandHandler("start", start(client_id=client_id, redirect_url=redirect_url, db=db)))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(
        MessageHandler(
            ~filters.COMMAND & ~filters.Document.FileExtension("fit") & ~filters.Document.FileExtension("tcx") & ~filters.Document.FileExtension("gpx"), other
        )
    )
    application.run_polling()


if __name__ == "__main__":
    main(TOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URL, STATUSES, USER_DB)
