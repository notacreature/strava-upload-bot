# TODO Вынести скоупы в константу/сеттинги

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
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from stravafunctions import (
    user_exists,
    scopes_valid,
    get_strava_refresh_token,
    get_strava_access_token,
    post_strava_activity,
    get_strava_upload,
    get_strava_activity,
    update_strava_activity,
)
from dictionary import MESSAGES, STATUSES

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
CLIENT_ID = CONFIG["Strava"]["CLIENT_ID"]
CLIENT_SECRET = CONFIG["Strava"]["CLIENT_SECRET"]
REDIRECT_URL = CONFIG["Server"]["URL"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()


# /start; регистрация
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    inline_key = InlineKeyboardButton(
        MESSAGES["key_auth"],
        url=f"http://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&scope=activity:read,activity:write&redirect_uri={REDIRECT_URL}?user_id={user_id}",
    )
    inline_keyboard = InlineKeyboardMarkup([[inline_key]])
    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            MESSAGES["reply_start"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
    else:
        await update.message.reply_text(
            MESSAGES["reply_restart"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )


# /favorites; создание списка избранных названий
async def favorites_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            MESSAGES["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            MESSAGES["reply_favorites"],
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
        MESSAGES["reply_done"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /delete; удаление данных пользователя из userdata.json
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            MESSAGES["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            MESSAGES["reply_delete"],
            constants.ParseMode.MARKDOWN,
        )
    return "delete_finish"


async def delete_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    USER_DB.remove(USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        MESSAGES["reply_done"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Публикация активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if not user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            MESSAGES["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    elif not scopes_valid(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            MESSAGES["reply_scopes"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    file_id = update.message.document.file_id
    file_data = await context.bot.get_file(file_id)
    data_type = str.split(update.message.document.file_name, ".")[-1]
    file = requests.get(file_data.file_path).content
    refresh_token = await get_strava_refresh_token(user_id, CLIENT_ID, CLIENT_SECRET, USER_DB, USER_QUERY)
    access_token = await get_strava_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    context.user_data["access_token"] = access_token

    upload_id = await post_strava_activity(access_token, data_type, file)
    upload = await get_strava_upload(upload_id, access_token, STATUSES)
    activity_id = upload["activity_id"]
    context.user_data["activity_id"] = activity_id

    if upload["status"] == STATUSES["ready"]:
        inline_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✏ Имя", callback_data="chname"),
                    InlineKeyboardButton("✏ Описание", callback_data="chdesc"),
                    InlineKeyboardButton("✏ Тип", callback_data="chtype"),
                ],
                [
                    InlineKeyboardButton(MESSAGES["key_activity"], url=f"https://www.strava.com/activities/{activity_id}"),
                ],
            ]
        )
        activity = await get_strava_activity(access_token, activity_id)
        await update.message.reply_text(
            MESSAGES["reply_published"] + "\n```\n" + str(activity) + "```",
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
    elif upload["status"] == STATUSES["error"]:
        await update.message.reply_text(
            f"{MESSAGES['reply_error']}`{upload['error']}`",
            constants.ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END
    elif upload["status"] == STATUSES["deleted"]:
        await update.message.reply_text(
            f"{MESSAGES['reply_error']}`{upload['status']}`",
            constants.ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    return "upload_change"


async def chname_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # favorites = USER_DB.get(USER_QUERY["user_id"] == user_id)["favorites"]
    # if favorites:
    #     activity_keyboard = ReplyKeyboardMarkup(
    #         [favorites],
    #         resize_keyboard=True,
    #         one_time_keyboard=True,
    #         input_field_placeholder=MESSAGES["placeholder_name"],
    #     )
    # await context.bot.send_message(
    #     user_id,
    #     MESSAGES["reply_name"],
    #     constants.ParseMode.MARKDOWN,
    #     reply_markup=activity_keyboard,
    # )
    return "chname_finish"


async def chdesc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        query.from_user.id,
        "🤖 Введи новое описание",
    )
    return "chdesc_finish"


async def chtype_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏊‍♀️ Swim", callback_data="swim"),
                InlineKeyboardButton("🚴‍♂️ Ride", callback_data="ride"),
                InlineKeyboardButton("👟 Run", callback_data="run"),
            ]
        ]
    )
    await query.edit_message_text(
        text="🤖 Выбери новый тип",
        reply_markup=inline_keyboard,
    )
    return "chtype_finish"


async def chname_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await update_strava_activity(access_token, activity_id, name=name)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏ Имя", callback_data="chname"),
                InlineKeyboardButton("✏ Описание", callback_data="chdesc"),
                InlineKeyboardButton("✏ Тип", callback_data="chtype"),
            ],
            [
                InlineKeyboardButton(MESSAGES["key_activity"], url=f"https://www.strava.com/activities/{activity_id}"),
            ],
        ]
    )
    await update.message.reply_text(
        MESSAGES["reply_updated"] + "\n```\n" + str(activity) + "```",
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


async def chdesc_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await update_strava_activity(access_token, activity_id, description=description)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏ Имя", callback_data="chname"),
                InlineKeyboardButton("✏ Описание", callback_data="chdesc"),
                InlineKeyboardButton("✏ Тип", callback_data="chtype"),
            ],
            [
                InlineKeyboardButton(MESSAGES["key_activity"], url=f"https://www.strava.com/activities/{activity_id}"),
            ],
        ]
    )
    await update.message.reply_text(
        MESSAGES["reply_updated"] + "\n```\n" + str(activity) + "```",
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


async def chtype_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sport_type = update.callback_query.data
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await update_strava_activity(access_token, activity_id, sport_type=sport_type)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏ Имя", callback_data="chname"),
                InlineKeyboardButton("✏ Описание", callback_data="chdesc"),
                InlineKeyboardButton("✏ Тип", callback_data="chtype"),
            ],
            [
                InlineKeyboardButton(MESSAGES["key_activity"], url=f"https://www.strava.com/activities/{activity_id}"),
            ],
        ]
    )
    await query.edit_message_text(
        MESSAGES["reply_updated"] + "\n```\n" + str(activity) + "```",
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


# /help; справка
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        MESSAGES["reply_help"],
        constants.ParseMode.MARKDOWN,
    )


# /cancel; отмена диалога ConversationHandler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        MESSAGES["reply_canceled"],
        constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# Обработка прочего текста
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        MESSAGES["reply_other"],
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
            MessageHandler(filters.Document.FileExtension("fit") | filters.Document.FileExtension("tcx") | filters.Document.FileExtension("gpx"), upload_start)
        ],
        states={
            # "upload_finish": [MessageHandler(~filters.COMMAND & filters.TEXT, upload_finish)],
            "upload_change": [
                CallbackQueryHandler(chname_start, pattern="chname"),
                CallbackQueryHandler(chdesc_start, pattern="chdesc"),
                CallbackQueryHandler(chtype_start, pattern="chtype"),
            ],
            "chname_finish": [MessageHandler(filters.TEXT, chname_finish)],
            "chdesc_finish": [MessageHandler(filters.TEXT, chdesc_finish)],
            "chtype_finish": [CallbackQueryHandler(chtype_finish, pattern="swim|ride|run")],
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
            ~filters.COMMAND & ~filters.Document.FileExtension("fit") & ~filters.Document.FileExtension("tcx") & ~filters.Document.FileExtension("gpx"), other
        )
    )
    application.run_polling()


if __name__ == "__main__":
    main()
