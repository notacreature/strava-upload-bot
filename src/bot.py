import os, requests, configparser, strava
from tinydb import TinyDB, Query
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
from dictionary import TEXT, URL

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
CLIENT_ID = CONFIG["Strava"]["CLIENT_ID"]
CLIENT_SECRET = CONFIG["Strava"]["CLIENT_SECRET"]
SCOPE = CONFIG["Strava"]["SCOPE"]
REDIRECT_URL = CONFIG["Server"]["URL"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()
PER_PAGE = 4


class KeyboardFormatter:
    @staticmethod
    def format_list_keyboard(keys: dict, page: int, per_page: int, activities: list) -> InlineKeyboardMarkup:
        inline_keys = [[]]

        if page == 1:
            inline_keys[0].append(InlineKeyboardButton(keys["key_refresh"], callback_data="Refresh"))
            inline_keys[0].append(InlineKeyboardButton(keys["key_next"], callback_data="NextPage"))
        elif page > 1:
            if len(activities) == per_page:
                inline_keys[0].append(InlineKeyboardButton(keys["key_prev"], callback_data="PrevPage"))
                inline_keys[0].append(InlineKeyboardButton(keys["key_next"], callback_data="NextPage"))
            elif len(activities) < per_page:
                inline_keys[0].append(InlineKeyboardButton(keys["key_prev"], callback_data="PrevPage"))
                inline_keys[0].append(InlineKeyboardButton(keys["key_refresh"], callback_data="Refresh"))

        for activity in activities:
            inline_keys.insert(-1, [InlineKeyboardButton(TEXT["key_activity"].format(activity["name"], activity["date"]), callback_data=activity["id"])])
        return InlineKeyboardMarkup(inline_keys)

    @staticmethod
    def format_activity_data(format: str, url: str, activity: dict) -> str:
        activity_link = url.format(activity["id"])
        return format.format(
            activity["name"],
            activity["sport_type"],
            activity["moving_time"],
            activity["distance"],
            activity["gear"],
            activity["description"],
            activity_link,
        )

    @staticmethod
    def format_edit_keyboard(keys: dict) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(keys["key_edit_name"], callback_data="EditName"),
                    InlineKeyboardButton(keys["key_edit_desc"], callback_data="EditDesc"),
                ],
                [
                    InlineKeyboardButton(keys["key_edit_type"], callback_data="EditType"),
                    InlineKeyboardButton(keys["key_edit_gear"], callback_data="EditGear"),
                ],
                [
                    InlineKeyboardButton(keys["key_activities"], callback_data="ShowActivities"),
                ],
            ]
        )

    @staticmethod
    def format_type_keyboard(keys: dict) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(keys["key_swim"], callback_data="Swim"),
                    InlineKeyboardButton(keys["key_ride"], callback_data="Ride"),
                    InlineKeyboardButton(keys["key_run"], callback_data="Run"),
                ]
            ]
        )

    @staticmethod
    def format_gear_keyboard(gears: dict) -> InlineKeyboardMarkup:
        inline_keys = []
        for gear in gears:
            inline_keys.append(
                [
                    InlineKeyboardButton(f"{gear['type']} {gear['name']} ({gear['converted_distance']} km)", callback_data=gear["id"]),
                ]
            )
        return InlineKeyboardMarkup(inline_keys)


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


# /delete; удаление данных пользователя из userdata.json
async def delete_user_data_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            TEXT["reply_delete_dialog"],
            constants.ParseMode.MARKDOWN,
        )
        return "delete_dialog"


async def delete_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    await strava.deauthorize(access_token)
    USER_DB.remove(USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        TEXT["reply_deleted"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Список последних тренировок
async def show_activities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_id = str(update.message.from_user.id)
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)

    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await context.bot.send_message(
            user_id,
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    context.user_data["access_token"] = access_token
    context.user_data["page"] = page = 1
    activity_list = await strava.get_activities(access_token, page, PER_PAGE)

    if update.message:
        await update.message.reply_text(
            TEXT["reply_activities_shown"],
            constants.ParseMode.MARKDOWN,
            reply_markup=KeyboardFormatter.format_list_keyboard(TEXT, page, PER_PAGE, activity_list),
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            TEXT["reply_activities_shown"],
            constants.ParseMode.MARKDOWN,
            reply_markup=KeyboardFormatter.format_list_keyboard(TEXT, page, PER_PAGE, activity_list),
        )
    return "activities_shown"


async def update_activities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    page = context.user_data["page"]

    if update.callback_query.data == "PrevPage":
        context.user_data["page"] = page = page - 1 if page > 1 else 1
    elif update.callback_query.data == "NextPage":
        context.user_data["page"] = page = page + 1

    activity_list = await strava.get_activities(access_token, page, PER_PAGE)

    await update.callback_query.edit_message_reply_markup(reply_markup=KeyboardFormatter.format_list_keyboard(TEXT, page, PER_PAGE, activity_list))
    return "activities_shown"


async def show_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["activity_id"] = activity_id = update.callback_query.data
    access_token = context.user_data["access_token"]
    activity = await strava.get_activity(activity_id, access_token)

    await update.callback_query.edit_message_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_shown"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


# Публикация тренировки
async def upload_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    context.user_data["access_token"] = access_token
    name = update.message.caption
    data_type = str.split(update.message.document.file_name, ".")[-1]
    file_data = await context.bot.get_file(update.message.document.file_id)
    file = requests.get(file_data.file_path).content
    upload_id = await strava.post_activity(access_token, name, data_type, file)
    upload = await strava.get_upload(upload_id, access_token)

    context.user_data["activity_id"] = activity_id = upload["activity_id"]
    if activity_id:
        activity = await strava.get_activity(activity_id, access_token)

        await update.message.reply_text(
            KeyboardFormatter.format_activity_data(TEXT["reply_activity_uploaded"], URL["activity"], activity),
            constants.ParseMode.MARKDOWN,
            reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
        )
        return "activity_shown"
    else:
        await update.message.reply_text(
            TEXT["reply_error"].format(str(upload["error"])),
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END


# Редактирование тренировки
async def edit_name_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    await context.bot.send_message(
        user_id,
        TEXT["reply_edit_name"],
        constants.ParseMode.MARKDOWN,
    )
    return "edit_name_dialog"


async def edit_desc_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    await context.bot.send_message(
        user_id,
        TEXT["reply_edit_desc"],
        constants.ParseMode.MARKDOWN,
    )
    return "edit_desc_dialog"


async def edit_type_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    await update.callback_query.edit_message_text(
        TEXT["reply_edit_type"],
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_type_keyboard(TEXT),
    )
    return "edit_type_dialog"


async def edit_gear_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    gears = await strava.get_gear(access_token)

    await update.callback_query.edit_message_text(
        TEXT["reply_edit_gear"],
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_gear_keyboard(gears),
    )
    return "edit_gear_dialog"


async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    activity_id = context.user_data["activity_id"]
    access_token = context.user_data["access_token"]
    name = update.message.text
    activity = await strava.update_activity(activity_id, access_token, name=name)

    await update.message.reply_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


async def edit_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    activity_id = context.user_data["activity_id"]
    access_token = context.user_data["access_token"]
    description = update.message.text
    activity = await strava.update_activity(activity_id, access_token, description=description)

    await update.message.reply_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


async def edit_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    activity_id = context.user_data["activity_id"]
    access_token = context.user_data["access_token"]
    sport_type = update.callback_query.data
    activity = await strava.update_activity(activity_id, access_token, sport_type=sport_type)

    await update.callback_query.edit_message_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


async def edit_gear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    activity_id = context.user_data["activity_id"]
    access_token = context.user_data["access_token"]
    gear_id = update.callback_query.data
    activity = await strava.update_activity(activity_id, access_token, gear_id=gear_id)

    await update.callback_query.edit_message_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


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

    delete_entry = CommandHandler("delete", delete_user_data_dialog)
    list_entry = CommandHandler("activities", show_activities)
    file_entry = MessageHandler(filters.Document.FileExtension("fit") | filters.Document.FileExtension("tcx") | filters.Document.FileExtension("gpx"), upload_activity)
    cancel_fallback = CommandHandler("cancel", cancel)
    start_reply = CommandHandler("start", start)
    help_reply = CommandHandler("help", help)
    other_reply = MessageHandler(~filters.COMMAND & ~filters.Document.FileExtension("fit") & ~filters.Document.FileExtension("tcx") & ~filters.Document.FileExtension("gpx"), other)

    activity_dialog = ConversationHandler(
        entry_points=[
            list_entry,
            file_entry,
        ],
        states={
            "activities_shown": [
                CallbackQueryHandler(show_activity, pattern="^\\d+$"),
                CallbackQueryHandler(update_activities, pattern="Refresh|NextPage|PrevPage"),
            ],
            "activity_shown": [
                CallbackQueryHandler(show_activities, pattern="ShowActivities"),
                CallbackQueryHandler(edit_name_dialog, pattern="EditName"),
                CallbackQueryHandler(edit_desc_dialog, pattern="EditDesc"),
                CallbackQueryHandler(edit_type_dialog, pattern="EditType"),
                CallbackQueryHandler(edit_gear_dialog, pattern="EditGear"),
            ],
            "edit_name_dialog": [MessageHandler(~filters.COMMAND & filters.TEXT, edit_name)],
            "edit_desc_dialog": [MessageHandler(~filters.COMMAND & filters.TEXT, edit_desc)],
            "edit_type_dialog": [CallbackQueryHandler(edit_type, pattern="Swim|Ride|Run")],
            "edit_gear_dialog": [CallbackQueryHandler(edit_gear, pattern="^\\w\\d+$")],
        },
        fallbacks=[
            cancel_fallback,
            list_entry,
            file_entry,
            delete_entry,
        ],
    )

    delete_dialog = ConversationHandler(
        entry_points=[
            delete_entry,
        ],
        states={
            "delete_dialog": [CommandHandler("delete", delete_user_data)],
        },
        fallbacks=[
            cancel_fallback,
            list_entry,
            file_entry,
            delete_entry,
        ],
    )

    application.add_handlers(
        [
            activity_dialog,
            delete_dialog,
            start_reply,
            help_reply,
            other_reply,
        ]
    )

    application.run_polling()


if __name__ == "__main__":
    main()
