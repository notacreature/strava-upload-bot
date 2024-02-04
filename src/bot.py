import os, requests, configparser, strava
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
from dictionary import TEXT, URL, STATUS

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
CLIENT_ID = CONFIG["Strava"]["CLIENT_ID"]
CLIENT_SECRET = CONFIG["Strava"]["CLIENT_SECRET"]
SCOPE = CONFIG["Strava"]["SCOPE"]
REDIRECT_URL = CONFIG["Server"]["URL"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()


# /start; регистрация
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_auth"], url=URL["auth"].format(CLIENT_ID, SCOPE, REDIRECT_URL, user_id)),
            ]
        ]
    )
    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_start"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            TEXT["reply_restart"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
        return ConversationHandler.END


# /favorites; создание списка избранных названий
async def favorites_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            TEXT["reply_favorites"],
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
        TEXT["reply_done"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /delete; удаление данных пользователя из userdata.json
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            TEXT["reply_delete"],
            constants.ParseMode.MARKDOWN,
        )
        return "delete_finish"


async def delete_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    await strava.deauthorize(access_token)
    USER_DB.remove(USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        TEXT["reply_done"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Публикация активности
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    file_id = update.message.document.file_id
    file_data = await context.bot.get_file(file_id)
    data_type = str.split(update.message.document.file_name, ".")[-1]
    file = requests.get(file_data.file_path).content
    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    context.user_data["access_token"] = access_token

    upload_id = await strava.post_activity(access_token, data_type, file)
    upload = await strava.get_upload(upload_id, access_token, STATUS)
    activity_id = upload["activity_id"]
    context.user_data["activity_id"] = activity_id

    if upload["status"] == STATUS["ready"]:
        inline_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(TEXT["key_chname"], callback_data="chname"),
                    InlineKeyboardButton(TEXT["key_chdesc"], callback_data="chdesc"),
                ],
                [
                    InlineKeyboardButton(TEXT["key_chtype"], callback_data="chtype"),
                    InlineKeyboardButton(TEXT["key_chgear"], callback_data="chgear"),
                ],
                [
                    InlineKeyboardButton(TEXT["key_openstrava"], url=URL["activity"].format(activity_id)),
                ],
            ]
        )
        activity = await strava.get_activity(access_token, activity_id)
        await update.message.reply_text(
            TEXT["reply_activityuploaded"].format(
                activity["name"], activity["sport_type"], activity["gear"], activity["moving_time"], activity["distance"], activity["description"]
            ),
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
        return "upload_change"
    elif upload["status"] == STATUS["error"]:
        await update.message.reply_text(
            TEXT["reply_error"].format(upload["error"]),
            constants.ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END
    elif upload["status"] == STATUS["deleted"]:
        await update.message.reply_text(
            TEXT["reply_error"].format(upload["status"]),
            constants.ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END


async def chname_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    favorites = USER_DB.get(USER_QUERY["user_id"] == user_id)["favorites"]
    reply_keyboard = ReplyKeyboardMarkup(
        [favorites],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=TEXT["placeholder_chname"],
    )
    await context.bot.send_message(
        user_id,
        TEXT["reply_chname"],
        constants.ParseMode.MARKDOWN,
        reply_markup=reply_keyboard,
    )
    return "chname_finish"


async def chdesc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        query.from_user.id,
        TEXT["reply_chdesc"],
        constants.ParseMode.MARKDOWN,
    )
    return "chdesc_finish"


async def chtype_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_swim"], callback_data="Swim"),
                InlineKeyboardButton(TEXT["key_ride"], callback_data="Ride"),
                InlineKeyboardButton(TEXT["key_run"], callback_data="Run"),
            ]
        ]
    )
    await query.edit_message_text(
        TEXT["reply_chtype"],
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "chtype_finish"


async def chgear_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    access_token = context.user_data["access_token"]
    gear_list = await strava.get_gear(access_token)
    inline_keys = []
    for gear in gear_list:
        inline_keys.append([InlineKeyboardButton(gear["type"] + " " + gear["name"], callback_data=gear["id"])])
    inline_keyboard = InlineKeyboardMarkup(inline_keys)
    await query.edit_message_text(
        TEXT["reply_chgear"],
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "chgear_finish"


async def chname_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await strava.update_activity(access_token, activity_id, name=name)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_chname"], callback_data="chname"),
                InlineKeyboardButton(TEXT["key_chdesc"], callback_data="chdesc"),
            ],
            [
                InlineKeyboardButton(TEXT["key_chtype"], callback_data="chtype"),
                InlineKeyboardButton(TEXT["key_chgear"], callback_data="chgear"),
            ],
            [
                InlineKeyboardButton(TEXT["key_openstrava"], url=URL["activity"].format(activity_id)),
            ],
        ]
    )
    await update.message.reply_text(
        TEXT["reply_activityupdated"].format(
            activity["name"], activity["sport_type"], activity["gear"], activity["moving_time"], activity["distance"], activity["description"]
        ),
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


async def chdesc_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await strava.update_activity(access_token, activity_id, description=description)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_chname"], callback_data="chname"),
                InlineKeyboardButton(TEXT["key_chdesc"], callback_data="chdesc"),
            ],
            [
                InlineKeyboardButton(TEXT["key_chtype"], callback_data="chtype"),
                InlineKeyboardButton(TEXT["key_chgear"], callback_data="chgear"),
            ],
            [
                InlineKeyboardButton(TEXT["key_openstrava"], url=URL["activity"].format(activity_id)),
            ],
        ]
    )
    await update.message.reply_text(
        TEXT["reply_activityupdated"].format(
            activity["name"], activity["sport_type"], activity["gear"], activity["moving_time"], activity["distance"], activity["description"]
        ),
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


async def chtype_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sport_type = update.callback_query.data
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await strava.update_activity(access_token, activity_id, sport_type=sport_type)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_chname"], callback_data="chname"),
                InlineKeyboardButton(TEXT["key_chdesc"], callback_data="chdesc"),
            ],
            [
                InlineKeyboardButton(TEXT["key_chtype"], callback_data="chtype"),
                InlineKeyboardButton(TEXT["key_chgear"], callback_data="chgear"),
            ],
            [
                InlineKeyboardButton(TEXT["key_openstrava"], url=URL["activity"].format(activity_id)),
            ],
        ]
    )
    await query.edit_message_text(
        TEXT["reply_activityupdated"].format(
            activity["name"], activity["sport_type"], activity["gear"], activity["moving_time"], activity["distance"], activity["description"]
        ),
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


async def chgear_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    gear_id = update.callback_query.data
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    activity = await strava.update_activity(access_token, activity_id, gear_id=gear_id)

    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_chname"], callback_data="chname"),
                InlineKeyboardButton(TEXT["key_chdesc"], callback_data="chdesc"),
            ],
            [
                InlineKeyboardButton(TEXT["key_chtype"], callback_data="chtype"),
                InlineKeyboardButton(TEXT["key_chgear"], callback_data="chgear"),
            ],
            [
                InlineKeyboardButton(TEXT["key_openstrava"], url=URL["activity"].format(activity_id)),
            ],
        ]
    )
    await query.edit_message_text(
        TEXT["reply_activityupdated"].format(
            activity["name"], activity["sport_type"], activity["gear"], activity["moving_time"], activity["distance"], activity["description"]
        ),
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "upload_change"


# /help; справка
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["reply_help"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /cancel; отмена диалога ConversationHandler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["reply_canceled"],
        constants.ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# Обработка прочих сообщений
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["reply_other"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    cancel_fallback = CommandHandler("cancel", cancel)
    file_entry = MessageHandler(
        filters.Document.FileExtension("fit") | filters.Document.FileExtension("tcx") | filters.Document.FileExtension("gpx"), upload_start
    )
    favorites_entry = CommandHandler("favorites", favorites_start)
    delete_entry = CommandHandler("delete", delete_start)

    start_reply = CommandHandler("start", start)
    help_reply = CommandHandler("help", help)
    other_reply = MessageHandler(
        ~filters.COMMAND & ~filters.Document.FileExtension("fit") & ~filters.Document.FileExtension("tcx") & ~filters.Document.FileExtension("gpx"), other
    )
    upload_dialog = ConversationHandler(
        entry_points=[file_entry],
        states={
            "upload_change": [
                CallbackQueryHandler(chname_start, pattern="chname"),
                CallbackQueryHandler(chdesc_start, pattern="chdesc"),
                CallbackQueryHandler(chtype_start, pattern="chtype"),
                CallbackQueryHandler(chgear_start, pattern="chgear"),
            ],
            "chname_finish": [MessageHandler(filters.TEXT, chname_finish)],
            "chdesc_finish": [MessageHandler(filters.TEXT, chdesc_finish)],
            "chtype_finish": [CallbackQueryHandler(chtype_finish, pattern="Swim|Ride|Run")],
            "chgear_finish": [CallbackQueryHandler(chgear_finish, pattern="^\w\d+$")],
        },
        fallbacks=[cancel_fallback, file_entry, favorites_entry, delete_entry],
    )
    favorites_dialog = ConversationHandler(
        entry_points=[favorites_entry],
        states={"favorites_finish": [MessageHandler(filters.TEXT, favorites_finish)]},
        fallbacks=[cancel_fallback, file_entry, favorites_entry, delete_entry],
    )
    delete_dialog = ConversationHandler(
        entry_points=[delete_entry],
        states={"delete_finish": [CommandHandler("delete", delete_finish)]},
        fallbacks=[cancel_fallback, file_entry, favorites_entry, delete_entry],
    )

    application.add_handlers(
        [
            upload_dialog,
            favorites_dialog,
            delete_dialog,
            start_reply,
            help_reply,
            other_reply,
        ]
    )

    application.run_polling()


if __name__ == "__main__":
    main()
