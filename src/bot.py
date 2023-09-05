# WIP Доработка: добавить проверку корректности scopes (готова функция)
# DONE Доработка: добавить зависимость команд /start, /help и /delete от наличия юзера в базе
# TODO Проверить и обновить текстовки
# WIP Рефакторинг по замечаниям Мити
# TODO Добавить пост-действия
# TODO Вынесениие текста в константы + i18n?
# TODO Баг: после успешной загрузки не удаляется ReplyKeyboard

import os, requests, aiofiles, configparser
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
USER_DB = TinyDB(
    os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json")
)
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


def check_scopes(user_id: str) -> bool:
    if not user_exists(user_id):
        return False
    else:
        scope = USER_DB.get(USER_QUERY["user_id"] == user_id)["scope"]
        if "activity:write" in scope:
            return True
        else:
            return False


def favorites_exists(user_id: str) -> bool:
    if not user_exists(user_id):
        return False
    else:
        favorites = USER_DB.get(USER_QUERY["user_id"] == user_id)["favorites"]
        if favorites:
            return True
        else:
            return False


# Обработка команды /start: вывод приветствия
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


# Обработка команды /help: вывод информационного сообщения
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    help_text = f"""🤖 Как помочь мне помочь вам опубликовать активность в Strava:\n
*1.* Откройте Strava по ссылке [https://www.strava.com/oauth](http://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&scope=activity:write&redirect_uri={REDIRECT_URI}?user_id={user_id}).
*2.* В открывшемся окне нажмите *Разрешить* – это позволит мне загружать файлы в ваш профиль.
*3.* Пришлите мне файл формата `.fit`, `.tcx` или `.gpx`.
*4.* Введите имя активности, выберите одно из последних или нажмите 💬, чтобы задать имя по умолчанию; команда /cancel отменит публикацию.
*5.* Ждите, я опубликую вашу активность в Strava."""
    await update.message.reply_text(help_text, constants.ParseMode.MARKDOWN)


# Обработка команды /cancel: отмена текущего диалога ConversationHandler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Действие отменено ↩️",
        constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# Обработка команды /favorites
async def favorites_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id):
        await update.message.reply_text(
            "🤖 ты кто такой сука?",
            constants.ParseMode.MARKDOWN,
        )
        return
    if not favorites_exists(user_id):
        await update.message.reply_text(
            "🤖 какого хуя они в другом порядке разложены?",
            constants.ParseMode.MARKDOWN,
        )
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
    return ConversationHandler.END


# Обработка команды /delete: удаление данных пользователя из userdata.json
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id):
        await update.message.reply_text(
            "🤖 ты кто такой сука? чтоб это сделать?",
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


# Необработка прочего текста
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 К сожалению, я не знаю, что на это ответить.\nПопробуйте ввести команду /help.",
        constants.ParseMode.MARKDOWN,
    )


# Получение файла и вход в диалог upload_dialog загрузки активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    file_id = update.message.document.file_id
    file_data = await context.bot.get_file(file_id)
    context.user_data["file_name"] = update.message.document.file_name
    context.user_data["file_path"] = file_data.file_path

    activity_keys = ["💬"]
    if not favorites_exists:
        return
    else:
        activity_keys = USER_DB.get(USER_QUERY["user_id"] == user_id)["favorites"]
        activity_keys.insert(0, "💬")

    activity_keyboard = ReplyKeyboardMarkup(
        [activity_keys],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Имя активности",
    )
    await update.message.reply_text(
        "🤖 Введите имя активности и я её опубликую.",
        constants.ParseMode.MARKDOWN,
        reply_markup=activity_keyboard,
    )
    return "upload_finish"


# Состояние upload_finish диалога upload_dialog: публикация активности и завершение диалога
async def upload_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    activity_name = update.message.text

    # Попытка получить refresh_token из хранилки; при неуспехе получаем от API
    try:
        refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    except (IndexError, KeyError):
        code = USER_DB.get(USER_QUERY["user_id"] == user_id)["auth_code"]
        url = f"https://www.strava.com/api/v3/oauth/token"
        params = {
            "client_id": f"{CLIENT_ID}",
            "client_secret": f"{CLIENT_SECRET}",
            "grant_type": "authorization_code",
            "code": f"{code}",
        }
        response = requests.post(url, params=params)
        refresh_token = response.json()["refresh_token"]

    # Получение access_token от Strava и обновление refresh_token в хранилке
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    access_token = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]
    USER_DB.update({"refresh_token": str(refresh_token)}, USER_QUERY["user_id"] == user_id)

    # Получение файла из API Telegram и запись в хранилку
    async with aiofiles.open(
        os.path.join(
            os.path.dirname(__file__), "..", "storage", context.user_data["file_name"]
        ),
        "wb",
    ) as bytes:
        await bytes.write(requests.get(context.user_data["file_path"]).content)

    # Загрузка файла в Strava
    async with aiofiles.open(
        os.path.join(
            os.path.dirname(__file__), "..", "storage", context.user_data["file_name"]
        ),
        "rb",
    ) as bytes:
        file = await bytes.read()
    url = "https://www.strava.com/api/v3/uploads"
    params = {
        "description": "Опубликовано с помощью https://t.me/StravaUploadActivityBot",
        "data_type": context.user_data["file_name"].split(".")[-1],
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {"file": file}
    if activity_name != "💬":
        params.update({"name": activity_name})
    response = requests.post(url, params=params, headers=headers, files=files)
    upload_id = response.json()["id_str"]

    # Проверка статуса загрузки
    url = f"https://www.strava.com/api/v3/uploads/{upload_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        response = requests.get(url, headers=headers)
        if response.json()["status"] == STATUSES["wait"]:
            pass
        elif response.json()["status"] == STATUSES["ready"]:
            inline_keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Посмотреть",
                            url=f"https://www.strava.com/activities/{response.json()['activity_id']}",
                        )
                    ]
                ]
            )
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

    # Очистка хранилки
    try:
        os.remove(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "storage",
                context.user_data["file_name"],
            )
        )
    except FileNotFoundError:
        pass

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
        states={
            "upload_finish": [
                MessageHandler(~filters.COMMAND & filters.TEXT, upload_finish)
            ]
        },
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
