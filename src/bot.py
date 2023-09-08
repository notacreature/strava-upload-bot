# DONE Доработка: добавить проверку корректности scopes (готова функция)
# DONE Доработка: добавить зависимость команд /start, /help и /delete от наличия юзера в базе
# TODO Проверить и обновить текстовки
# WIP Рефакторинг по замечаниям Мити
# TODO Вынесение текста в константы + i18n?
# TODO Добавить пост-действия
# TODO Баг: после успешной загрузки не удаляется ReplyKeyboard

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
REDIRECT_URI = CONFIG["Server"]["URL"]
USER_QUERY = Query()
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
STATUSES = {
    "ready": "Your activity is ready.",
    "wait": "Your activity is still being processed.",
    "deleted": "The created activity has been deleted.",
    "error": "There was an error processing your activity.",
}


def user_exists(user_id: str) -> bool:
    user = USER_DB.search(USER_QUERY["user_id"] == user_id)
    if user:
        return True
    else:
        return False


def scopes_met(user_id: str) -> bool:
    if not user_exists(user_id):
        return False
    else:
        scope = USER_DB.get(USER_QUERY["user_id"] == user_id)["scope"]
        if "activity:write" in scope:
            return True
        else:
            return False


async def get_strava_refresh_token(user_id: str) -> str:
    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    if not refresh_token:
        url = f"https://www.strava.com/api/v3/oauth/token"
        code = USER_DB.get(USER_QUERY["user_id"] == user_id)["auth_code"]
        params = {
            "client_id": f"{CLIENT_ID}",
            "client_secret": f"{CLIENT_SECRET}",
            "grant_type": "authorization_code",
            "code": f"{code}",
        }
        response = requests.post(url, params=params)
        refresh_token = response.json()["refresh_token"]
    return refresh_token


async def get_strava_access_token(user_id: str, refresh_token: str) -> str:
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    refresh_token = response.json()["refresh_token"]
    USER_DB.update({"refresh_token": str(refresh_token)}, USER_QUERY["user_id"] == user_id)
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
        if activity_name != "💬"
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Открыть Strava 🔑",
                    url=f"http://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&scope=activity:write&redirect_uri={REDIRECT_URI}?user_id={user_id}",
                )
            ]
        ]
    )
    if not user_exists(user_id):
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


# /help; справка
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    help_text = f"""🤖 Как помочь мне помочь вам опубликовать активность в Strava:\n
*1.* Откройте Strava по ссылке [https://www.strava.com/oauth](http://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&scope=activity:write&redirect_uri={REDIRECT_URI}?user_id={user_id}).
*2.* В открывшемся окне нажмите *Разрешить* – это позволит мне загружать файлы в ваш профиль.
*3.* Пришлите мне файл формата `.fit`, `.tcx` или `.gpx`.
*4.* Введите имя активности, выберите одно из последних или нажмите 💬, чтобы задать имя по умолчанию; команда /cancel отменит публикацию.
*5.* Ждите, я опубликую вашу активность в Strava."""
    await update.message.reply_text(help_text, constants.ParseMode.MARKDOWN)


# /cancel; отмена диалога ConversationHandler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Действие отменено ↩️",
        constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# /favorites; создание списка избранных названий
async def favorites_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id):
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


async def favorites_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    favorites = update.message.text.split(",")[:3]
    for fav in favorites:
        fav.strip()
    USER_DB.upsert({"favorites": favorites}, USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        f"🤖 готово {favorites}",
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /delete; удаление данных пользователя из userdata.json
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id):
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


async def delete_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    USER_DB.remove(USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        "🤖 Готово, я вас больше не помню.",
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Обработка прочего текста
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 К сожалению, я не знаю, что на это ответить.\nПопробуйте ввести команду /help.",
        constants.ParseMode.MARKDOWN,
    )


# Публикация активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if not user_exists(user_id):
        await update.message.reply_text(
            "🤖 ты кто такой сука?",
            constants.ParseMode.MARKDOWN,
        )
        return
    elif not scopes_met(user_id):
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
    favorites = USER_DB.get(USER_QUERY["user_id"] == user_id)["favorites"]
    for fav in favorites:
        activity_keys.append(fav)
    activity_keyboard = ReplyKeyboardMarkup(
        [activity_keys],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Название активности",
    )
    await update.message.reply_text(
        "🤖 Введите имя активности и я её опубликую.",
        constants.ParseMode.MARKDOWN,
        reply_markup=activity_keyboard,
    )
    return "upload_finish"


async def upload_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    activity_name = update.message.text
    refresh_token = await get_strava_refresh_token(user_id)
    access_token = await get_strava_access_token(user_id, refresh_token)
    data_type = context.user_data["file_name"].split(".")[-1]
    file = requests.get(context.user_data["file_path"]).content

    upload_id = await upload_strava_activity(access_token, activity_name, data_type, file)

    url = f"https://www.strava.com/api/v3/uploads/{upload_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:  # Проверка статуса загрузки
        response = requests.get(url, headers=headers)
        if response.json()["status"] == STATUSES["wait"]:
            continue
        elif response.json()["status"] == STATUSES["ready"]:
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
        elif response.json()["status"] == STATUSES["error"]:
            await update.message.reply_text(
                f"Не удалось загрузить активность 💢\nДетали: `{response.json()['error']}`",
                constants.ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove(),
            )
            break
        elif response.json()["status"] == STATUSES["deleted"]:
            await update.message.reply_text(
                f"Не удалось загрузить активность 💢\nДетали: `{response.json()['status']}`",
                constants.ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove(),
            )
            break

    return ConversationHandler.END


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
                filters.Document.FileExtension("fit")
                | filters.Document.FileExtension("tcx")
                | filters.Document.FileExtension("gpx"),
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
            ~filters.COMMAND
            & ~filters.Document.FileExtension("fit")
            & ~filters.Document.FileExtension("tcx")
            & ~filters.Document.FileExtension("gpx"),
            other,
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()
