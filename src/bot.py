# TODO Доработка: заменить последние названия активностей на Избранные
# TODO Доработка: добавить проверку корректности scope'ов
# TODO Доработка: добавить зависимость команд /start, /help и /delete от наличия юзера в базе
# TODO Рефакторинг по замечаниям Мити
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

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))


# Обработка команды /start: вывод приветствия
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    client_id = config["Strava"]["CLIENT_ID"]
    redirect_uri = config["Server"]["URL"]
    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Открыть Strava 🔑",
                    url=f"http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&scope=activity:write&redirect_uri={redirect_uri}?user_id={user_id}",
                )
            ]
        ]
    )
    await update.message.reply_text(
        "🤖 Привет! Я помогу вам опубликовать активность в Strava.\nДля начала, разрешите мне загружать файлы в ваш профиль Strava.",
        reply_markup=inline_keyboard,
    )


# Обработка команды /help: вывод информационного сообщения
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    client_id = config["Strava"]["CLIENT_ID"]
    redirect_uri = config["Server"]["URL"]
    help_text = f"""🤖 Как помочь мне помочь вам опубликовать активность в Strava:\n
*1.* Откройте Strava по ссылке [https://www.strava.com/oauth](http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&scope=activity:write&redirect_uri={redirect_uri}?user_id={user_id}).
*2.* В открывшемся окне нажмите *Разрешить* – это позволит мне загружать файлы в ваш профиль.
*3.* Пришлите мне файл формата `.fit`, `.tcx` или `.gpx`.
*4.* Введите имя активности, выберите одно из последних или нажмите 💬, чтобы задать имя по умолчанию; команда `\cancel` отменит публикацию.
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


# Обработка команды /delete: удаление данных пользователя из userdata.json
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Вы точно хотите чтобы я удалил все данные о вас? Я не смогу загружать ваши файлы пока вы снова не авторизуете меня в Strava.\nДля подтверждения повторите команду `/delete`, для отмены введите `/cancel`.",
        constants.ParseMode.MARKDOWN,
    )

    return "delete_finish"


async def delete_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_db = TinyDB(
        os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json")
    )
    user_query = Query()

    user_db.remove(user_query["user_id"] == user_id)
    await update.message.reply_text(
        "🤖 Готово, я вас больше не знаю.",
        constants.ParseMode.MARKDOWN,
    )

    return ConversationHandler.END


# Необработка прочего текста
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 К сожалению, я не знаю, что на это ответить.\nПопробуйте ввести команду `/help`.",
        constants.ParseMode.MARKDOWN,
    )


# Получение файла и вход в диалог upload_dialog загрузки активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    file_id = update.message.document.file_id
    file_data = await context.bot.get_file(file_id)
    context.user_data["file_name"] = update.message.document.file_name
    context.user_data["file_path"] = file_data.file_path
    user_db = TinyDB(
        os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json")
    )
    user_query = Query()

    activity_names = ["💬"]
    try:
        for name in user_db.get(user_query["user_id"] == user_id)["activity_names"]:
            activity_names.append(name)
    except KeyError:
        pass

    name_keyboard = ReplyKeyboardMarkup(
        [[(name) for name in activity_names]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Имя активности",
    )
    await update.message.reply_text(
        "🤖 Введите имя активности и я её опубликую.", reply_markup=name_keyboard
    )

    return "upload_finish"


# Состояние upload_finish диалога upload_dialog: публикация активности и завершение диалога
async def upload_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    activity_name = update.message.text
    client_id = config["Strava"]["CLIENT_ID"]
    client_secret = config["Strava"]["CLIENT_SECRET"]
    user_db = TinyDB(
        os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json")
    )
    user_query = Query()

    # Попытка получить refresh_token из хранилки; при неуспехе получаем от API
    try:
        refresh_token = user_db.get(user_query["user_id"] == user_id)["refresh_token"]
    except (IndexError, KeyError):
        code = user_db.get(user_query["user_id"] == user_id)["auth_code"]
        url = f"https://www.strava.com/api/v3/oauth/token"
        params = {
            "client_id": f"{client_id}",
            "client_secret": f"{client_secret}",
            "grant_type": "authorization_code",
            "code": f"{code}",
        }
        response = requests.post(url, params=params)
        refresh_token = response.json()["refresh_token"]

    # Получение access_token от Strava и обновление refresh_token в хранилке
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    access_token = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]
    user_db.update({"refresh_token": refresh_token}, user_query["user_id"] == user_id)

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
                "Активность опубликована 🏆", reply_markup=inline_keyboard
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

    # Обновление списка последних имен Активности
    activity_names = []
    try:
        for name in user_db.get(user_query["user_id"] == user_id)["activity_names"]:
            activity_names.append(name)
        if (activity_name not in activity_names) & (activity_name != "💬"):
            activity_names.append(activity_name)
            if len(activity_names) > 3:
                activity_names.pop(0)
        user_db.update(
            {"activity_names": activity_names}, user_query["user_id"] == user_id
        )
    except KeyError:
        if activity_name != "💬":
            activity_names.append(activity_name)
            user_db.update(
                {"activity_names": activity_names}, user_query["user_id"] == user_id
            )

    return ConversationHandler.END


def main():
    token = config["Telegram"]["BOT_TOKEN"]
    application = ApplicationBuilder().token(token).build()
    delete_dialog = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={"delete_finish": [CommandHandler("delete", delete_finish)]},
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
